"""Builder implementation. pack_builder.py embeds this and all DAT sources.

Run the GENERATED build_garden_td.py in a TD Text DAT, not this template.
"""


def build(sources):
    project_comp = op("/project1")
    if project_comp is None:
        raise RuntimeError("需要 /project1。请在标准 TouchDesigner 工程中运行 builder。")
    garden = project_comp.op("garden")
    if garden is None:
        garden = project_comp.create(baseCOMP,"garden")
    elif garden.fetch("breathing_garden_owned",False) is not True:
        raise RuntimeError("/project1/garden 已存在且不是本 builder 创建；为保护已有内容，请先重命名它。")
    garden.store("breathing_garden_owned",True)
    # Rebuild only owned children. Preserve arbitrary user nodes and live source.
    prior_controls = garden.op("garden_controls")
    live_path = prior_controls.par.Livechop.eval() if prior_controls else ""
    old_execute = garden.op("frame_execute")
    if old_execute:
        old_execute.par.active = False
    owned = garden.fetch("owned_nodes",[])
    for name in owned:
        node = garden.op(name)
        if node:
            node.destroy()
    created = []
    notes = []

    def make(kind,name,parent_comp=None):
        owner = parent_comp or garden
        existing = owner.op(name)
        if existing:
            raise RuntimeError("保留用户节点而停止：名称冲突 " + existing.path)
        node = owner.create(kind,name)
        if owner == garden:
            created.append(name)
            # Incremental ownership makes a failed build safely rerunnable.
            garden.store("owned_nodes",list(created))
        return node

    def setting(node,name,value,required=True):
        parameter = getattr(node.par,name,None)
        if parameter is None:
            message = "{} 缺少参数 {} (build {})".format(node.path,name,app.build)
            notes.append(message)
            print("[Breathing Garden] " + message)
            if required:
                raise RuntimeError(message)
            return False
        try:
            if parameter.isMenu and isinstance(value,str) and value not in parameter.menuNames:
                raise ValueError("菜单可选值："+repr(parameter.menuNames))
            parameter.val = value
        except Exception as error:
            message = "{}.{} = {!r}: {}".format(node.path,name,value,error)
            notes.append(message)
            if required:
                raise RuntimeError(message)
            print("[Breathing Garden] " + message)
            return False
        return True

    def dat(name,filename,parent_comp=None,kind=None):
        node = make(kind or textDAT,name,parent_comp)
        node.text = sources[filename]
        return node

    engine = dat("garden_engine","garden_engine.py")
    runtime = dat("garden_runtime","garden_runtime.py")
    dat("validate_garden","validate_garden_td.py")
    controls = make(baseCOMP,"garden_controls")
    page = controls.appendCustomPage("Garden")
    mode = page.appendMenu("Mode",label="Input Mode")[0]
    mode.menuNames = ["TEST_MODE","LIVE_MODE"]
    mode.menuLabels = ["TEST_MODE · 模拟输入","LIVE_MODE · 真实追踪"]
    mode.val = "TEST_MODE"
    quality = page.appendMenu("Quality")[0]
    quality.menuNames = ["NORMAL","LOW"]
    quality.menuLabels = ["NORMAL","LOW"]
    quality.val = "NORMAL"
    page.appendCHOP("Livechop",label="Live Tracking CHOP")[0].val = live_path
    page.appendStr("Handsource",label="Optional Stage3 hand CHOP")[0].val = "/project1/hand_tracking/normalized_data"
    page.appendStr("Facesource",label="Optional Stage3 face CHOP")[0].val = "/project1/face_tracking/blend_shapes"
    page.appendToggle("Adapterflipy",label="Stage3 adapter source Y is bottom-up")[0].val = True
    for name,label,value,lo,hi in (
        ("Growstep","Growth step / 30 Hz",.0056,.0005,.02),
        ("Branchprob","Branch probability",.018,0,.08),
        ("Lifefull","Life full / seconds",48,5,180),
        ("Lifefade","Life fade / seconds",13,2,45),
        ("Brightness","Life brightness",.86,.1,1.5),
        ("Linewidth","Fine line width",.8,.25,2),
        ("Bloom","Soft bloom intensity",.24,0,1)):
        par = page.appendFloat(name,label=label)[0]
        par.val = value
        par.min,par.max = lo,hi
        par.normMin,par.normMax = lo,hi
        par.clampMin = par.clampMax = True
    page.appendInt("Seed",label="Reproducible random seed")[0].val = 17
    page.appendToggle("Debug",label="Development diagnostics")[0].val = False
    page.appendToggle("Autolow",label="Auto LOW after sustained slow FPS")[0].val = True
    page.appendPulse("Reset",label="Reset garden")
    page.appendInt("Resetserial")[0].val = 0
    defaults = make(constantCHOP,"input_defaults")
    test = make(constantCHOP,"input_test")
    for chop in (defaults,test):
        chop.par.const.sequence.numBlocks = 7
        for i,name in enumerate(engine.module.CHANNELS):
            setting(chop,"const{}name".format(i),name)
            setting(chop,"const{}value".format(i),.5 if name in ("tip_u","tip_v") else 0)
    live = make(selectCHOP,"input_live")
    adapter = make(scriptCHOP,"stage3_adapter")
    adapter_callback = garden.op("stage3_adapter_callbacks")
    if adapter_callback is None:
        adapter_callback = dat("stage3_adapter_callbacks","stage3_tracking_adapter.py")
    else:
        # Like Script SOP, Script CHOP creates its own callback DAT.
        adapter_callback.text = sources["stage3_tracking_adapter.py"]
        created.append(adapter_callback.name)
        garden.store("owned_nodes",list(created))
    setting(adapter,"callbacks",adapter_callback.path)
    if not live_path and op("/project1/hand_tracking/normalized_data") is not None:
        controls.par.Livechop = adapter.path
    live.par.chop.expr = "parent().op('garden_controls').par.Livechop.eval() or parent().op('input_defaults')"
    switch = make(switchCHOP,"switch_tracking")
    switch.inputConnectors[0].connect(test)
    switch.inputConnectors[1].connect(live)
    switch.par.index.expr = "1 if parent().op('garden_controls').par.Mode.eval() == 'LIVE_MODE' else 0"
    tracking = make(nullCHOP,"null_tracking")
    tracking.inputConnectors[0].connect(switch)
    geo = make(geometryCOMP,"geo_growth")
    for child in list(geo.children):
        child.destroy()  # only factory-created default SOPs inside this new geo
    sop = make(scriptSOP,"branches_sop",geo)
    # Script SOP auto-creates this DAT in current TD builds. Reuse only that
    # factory callback inside the geometry COMP created above.
    callback = geo.op("branches_sop_callbacks")
    if callback is None:
        callback = dat("branches_sop_callbacks","branches_sop_callbacks.py",geo)
    else:
        callback.text = sources["branches_sop_callbacks.py"]
    setting(sop,"callbacks",callback.path)
    sop.display = sop.render = True
    sop.viewer = False
    mat = make(lineMAT,"line_growth")
    setting(mat,"drawlines",True)
    setting(mat,"drawpoints",False)
    setting(mat,"drawvectors",False)
    # New TD builds upload SOP Cd to the GPU as Color. Hard-coding Cd here
    # silently renders every line white in 2025. Keep the factory GPU binding,
    # while Script SOP always stores the requested Cd RGBA point attribute.
    gpu_color_attribute = "Color" if mat.par.linecoloratt.eval() == "Color" else "Cd"
    setting(mat,"linecoloratt",gpu_color_attribute)
    garden.store("gpu_color_attribute",gpu_color_attribute)
    notes.append("SOP Cd RGBA -> Line MAT GPU attribute " + gpu_color_attribute)
    setting(mat,"linenearcolorr",1)
    setting(mat,"linenearcolorg",1)
    setting(mat,"linenearcolorb",1)
    setting(mat,"linenearalpha",1)
    setting(mat,"specifylinefarcolor",False)
    setting(mat,"blending",True)
    # Keep point RGB straight until the framebuffer blend. In TD 2025 shader
    # pre-multiplication interacts with color conversion and over-darkens dim
    # points. The GPU integration test measures alpha .25 => luminance .25.
    setting(mat,"pointcolorpremult","alreadypremult")
    setting(mat,"postmultalpha",False)
    setting(mat,"srcblend","sa")
    setting(mat,"destblend","omsa")
    setting(mat,"separatealphafunc",True)
    setting(mat,"srcblenda","one")
    setting(mat,"destblenda","omsa")
    setting(mat,"depthwriting",False)
    setting(mat,"depthtest",False,False)
    setting(mat,"linestartcaptype","round",False)
    setting(mat,"lineendcaptype","round",False)
    # Parameter names are verified against the installed TD before delivery.
    width_name = next((n for n in ("widthnear","width","linewidth","linenearwidth") if getattr(mat.par,n,None) is not None),None)
    if width_name:
        getattr(mat.par,width_name).expr = "parent().op('garden_controls').par.Linewidth"
        if getattr(mat.par,"widthfar",None) is not None:
            mat.par.widthfar.expr = "parent().op('garden_controls').par.Linewidth"
    else:
        raise RuntimeError("Line MAT 缺少线宽参数，请在 build_log 中查看版本诊断。")
    material_name = "material" if getattr(geo.par,"material",None) is not None else "mat"
    setting(geo,material_name,mat.path)
    setting(geo,"render",True)
    camera = make(cameraCOMP,"cam1")
    setting(camera,"projection","ortho")
    setting(camera,"orthowidth",2.0)
    setting(camera,"tz",5)
    setting(camera,"near",.1)
    setting(camera,"far",10)
    setting(camera,"bgcolora",0)
    render = make(renderTOP,"render1")
    setting(render,"camera",camera.path)
    setting(render,"geometry",geo.path)
    setting(render,"lights","")
    setting(render,"outputresolution","custom")
    setting(render,"resolutionw",1280)
    setting(render,"resolutionh",720)
    setting(render,"antialias","aa4")
    setting(render,"format","rgba16float")
    for name,value in zip(("bgcolorr","bgcolorg","bgcolorb"),engine.module.BACKGROUND):
        setting(render,name,value)
    setting(render,"bgcolora",1)
    bloom = make(bloomTOP,"bloom1")
    bloom.inputConnectors[0].connect(render)
    setting(bloom,"preblacklevel",.035)
    setting(bloom,"minbloomradius",.03)
    setting(bloom,"maxbloomradius",.24)
    setting(bloom,"bloomthreshold",.01)
    setting(bloom,"bloomfill",.08)
    setting(bloom,"bloomintensity",.24)
    bloom.par.bloomintensity.expr = "parent().op('garden_controls').par.Bloom"
    output = make(nullTOP,"out1")
    output.inputConnectors[0].connect(bloom)
    output.viewer = True
    garden.par.opviewer = output.path
    reset = dat("reset_controls","reset_controls.py",kind=parameterexecuteDAT)
    setting(reset,"op",controls.path)
    setting(reset,"pars","Reset")
    setting(reset,"valuechange",False)
    setting(reset,"onpulse",True)
    diagnostics = make(textDAT,"diagnostics")
    diagnostics.text = "Development HUD disabled. Run validate_garden.module.validate() or enable Debug."
    log = make(textDAT,"build_log")
    log.text = "TouchDesigner {}\n".format(app.build)+"\n".join(notes or ["Required parameters configured."])
    execute = dat("frame_execute","frame_execute_callbacks.py",kind=executeDAT)
    setting(execute,"framestart",True)
    setting(execute,"active",True)
    # Only the garden's nodes are laid out; the surrounding project is untouched.
    for i,node in enumerate(garden.children):
        node.nodeX = (i%5)*210
        node.nodeY = -(i//5)*150
    garden.nodeX, garden.nodeY = 0,-500
    runtime.module.reset(garden)
    sop.cook(force=True)
    # A known initial SOP cook ensures dust is visible even before the timeline
    # plays. All simulation frames are driven by frame_execute thereafter.
    output.cook(force=True)
    print("[Breathing Garden] Ready: /project1/garden/out1 · TEST_MODE")
    return garden
