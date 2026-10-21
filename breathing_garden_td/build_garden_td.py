"""自包含 TD builder。复制完整内容到 Text DAT，Run Script。
由 pack_builder.py 生成；内置纯 Python 引擎与全部回调，无外部文件依赖。"""
import base64, json, zlib

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


_PAYLOAD = 'c-rlK4RhN#lIUN-IkmN<MA4%Bk;F4fohNoaZk^a?JG-|pcByERvN)kg9!c5Kq;kLgx*Grqkf7}B-mCZO)tgKriD)!{Mx(#b0Kf0t`$ZU~vnaif)5y&?J4bBihW=bHBKBJm`PCv$@7a5TbJ<npry+bFCGlP17aLZ_%T?l6ahCqV(u`f7><0caDts0%^Q@>!_a?nbFS0U5kdi@d7RDuD38Ip%%82>wF)NagWpnlzht+~j2xt+-_lt^ot~WVw*~c_rRqTPq<xN^;`6$dDp)-E?fOssM`9TonRmq~n&&w!eWfWv-SUS+9ip>k?5ldIgyQnB#b_}Ia2tb#g-`}Lzme2Oa?86^y9<Q-(73J((1phQ+V?~q~S-1+~y9Byi!5HTAsEE=EO42YYSm9R@4VIHH<-=!7pkMu?fX1@rO*${KB@6w^4-&sDfexa)e&j$`q9jDpz5Q_f`Sa=76`L~aW~Ykt+3IG;Vf^cZ_*(eEw<zR4!oq*#-|{#O7X0fnTUFv~xr~$OX2-rse>;Brm-m<FUp}88^2zSx;J{&r{KNC`6M#N_{CthY-uQr*Oyn2u)k^_$e#SBE2^3@g`BLKe+wtWm4ltHDJb~k2Pr!Wm`2NEg{H4Yw-b+#LjsbdKBEmmmG-p7hWp1q<mSod0f-K@GfZ9hlDTDuts9F^%(0*+tnZuTGYAs@it!)JbX9w%SPgaq`;EBIVDnurcRK-So!~X~lx;9TTzv8v*rc^Y@f#NyMx*M1CIE|}FKm%_Aw~K~&)o6`e%dEd5z-durg~P5lIsa-Ob@11f<sc%zjI65eG4zj9rm{6cRD)_@?TsdbN)X^*YfigK>4Uw^(s_I@5CK#CZT8`R9kDn?oO@&C@zwR|#Ste16uIN^!67gG?eh5Z+Yhsg%k$rkfBSg$@%ry7nD>f9eLDV+*~#g}^@kdH^ZerM`1AFZEO^}%T%ErEbP7eYi_=REC4mkP#|_x^`StNx4J<)`=>*Kx_2v0rP66QbWOj9N{PyGL_evK*&gfvrpDxZ$4S?gZ=-SEOPS3Etx96Wvt`vZm6Se&E_~hdkwRk+)=jCS~-<{6heKFzKf2D#PpPY6<JVCk3)9a6yhVp$^jOXOz)z$ggUkxC8u4v}u%hmPlEl7fzu-<EhuouUd*B{@Woz^tn*U0|y!Z0&?lLq45+4<j2FAYF~5bsZ~uD`$-K7b%m33VuE<kR{2^#=o`YY1%R<L8Sn*Ry~7@=4{-NzI+7$AAKQ@bO$}<G`KBa+E!vPp?$;uSDgyUoQW8j6KviT5!Sfm+SKx3~=`DLZ$u$*BO@oD=n~PR4uZQKf#qd&x+Z9uKXmfHdc^;z!yKJH#?utFFzfhfrM5B0LT;pz@}3W;?UmBj#92HcEDzJSHslXAA_7Uucqn#{@BrxDgQOhG4&1vj+!H;lh@*r&IZ%T7K}!onC^82DvqUBWW6u4$7*pM=YkGvL4E#fqy6&J`y|qygdlkr#D`K;E`1Q!>HQ4#f2ov|x&N5Xs(7g*$QK}dn+XTa(bv(d=za;7!ZW&=>V>IZdKVYfqT7*XB-jnn=c>rQ0oYxZCGhl}54xwXd+(C$F)E(XyPoz{LI_&=VZ18aBG26VMdH__i9?0#J*`2dY6d`HVg_iLbs_lJXL$xt(1`@BO;p@yP+3BQ&gM`#D>hRs6l_=WS^9|@_r!qEf&3>b&57DSQ^5}-;7Kqqk8o%Vmp@2?hX}1q6`-i1u*HvcakwhTj#br%1VC$eCT;R(G4utr6$h}Op5~bcz3|~#9F@fL=m|E%KfE(1(OtH}o;SjEHbcW}HnYkonX6(Hf4kC@6N^GC3&28;VZ43i(!Z$5Bb!|1Sc@8T7|g|eRDo3qe-~L2s$Jk^fB=`K#ednFpcfGTGHrFKCGPb?r`<o<hnf#MV;D}MgH2gpL=SPcD%n&alh!f4HuIv<YxZVJBQ*6*(wX<9Bim(rj@Dc=uiWG8n^lL{cIv%!SU{%h^mCR*ow?>^XczM@Ss^T4%Wgp;IvRQuwn~Z=5pdtly`&Ed!P*#*W7UOM7l3oRB1bYSjOAgG<vFZD;j|iIaukzT^!2t~A{L{uFkF$4`TA9k#9gH^*d9x3<bii(JFHva9vn`<^`Z~ESBZD(ff+z<Pvx)dTeNT341_t-?Vhg-F&S=SPuT75rqLRNJI;gGp<x9gkC)+0w}}8wIO%Raiv|erif0Oon{bFAg}Jl@zbZkkvJEJFjFMyqa&$pc-3!snD!h0e7c>l$1VZ<IcF!f06n!0LCeQy#C=oX3X^27wQW#Lsz}RCXX~_xF5i}1G=h^Q!J3{S&(aOdYrHIQiOCF-;2~J(}>-W_%=f8f`hI9_=Br2*+BNBwpo&_+#sw3@%pea{ND~VDoccqHAi9K^<Pi1l0syvsWB`#}(&;!YiBm+k4NSj9RV$^|R5+cGNN^FJtFW6bUj4KxSRj?SXa^}y$o&oLdCrSAWOM!6Ey{N!-#lUY^l|IUaY|gIEFNCVWSd+xZqhGxBIJN5Dx|0L@30VV5K!A@VmMzi?pbb!HFYD7El7+FWu6hwuXkZ=}$Wq-VP_KAnR4id-QY*SNt*PBE8-=P`)rE9R^VNl9`df02QCWQdfm*zchz2~=gp}kpEK>Oh4J)8P8U>Zv8hJvnwZv9iQ2jq7niQJF80{5H4~<Wn1BGzG{9cZobC<fbK7nKrvlpjeRRCqds*ZSYu4MNh0Fq4|8Ozumn3e2K2D+71g|%jW0(K`d^N5sNw9YNytX<FDw~g`=xWeKwII;Y(|1Q`+Rvm=3ZF|(zum?>$ZIwepcN<0-%as`E_ZEze#P8y&gUGgxi%&+6gzblMbQOhZWvaYx<5Z*>_(;%~5y-MQ3xUdUcn@;`Q&VozY5_)m05g$b7_&45Gn!{Bhdn^I)&BBOxb3tbK2UI5>HCVsB{4iU{Gk58QGv|0^mwhH%^!}4_TKEIeo9m(z3~U?4Qu5**tUrZy;{{wr|rXr6~)@~zq0MY1kE?gJs4>v&?9?5J0^D5aMvUW?t0Lm(eJaM$ms$B8{kTFTd_66fViUnT5IjwmT-J(<R(dnyBLjvGp|DIogN#s`)xWTrKCmuSn>kJ=BpKmQOh4%cO%~(@HTP6edi9R{Es-dwAv2hRQ37{c#+STE)QMd9d;KT->eZU?vQ(oI4U(Fsx$ze){F$G!|0>d2(?h{Z%XV2J-aQSRoxu%3oaJ=Wnuwo&&|@vFRXz^CmktK=t+Dt1nbA6GPb7Kl*QffcWc%<wIru&0sF4wW74A<>aA5wiuL&l)`ZMp#;B57#fS9nRIfewX6!P=-qXbyH{)j@6t_-I&zP<YHKKrP&NTH;nKREYot|g)JadBjCr2?^KyX8uuvy5Ta2N&crZ+oO2DSz6zsf*d$AN&EqiSvw@52yK9qT*Vt|&Tnr@Z+-h@ukV4q+1;;bdn~@yf5LyA`uu-+gLhQ6i*nkf3BRC?;hZr=ngQ9{pqU-N!r1Of7v34r4Q7w$={YIDChoH6iFVstzKq6?O2+rlsB&5S$SOUNE3xS-H{Qq$$^?Oqp&lYluTS%Uht90@P18R^G=mW;eHYaSI;iEts6AR+Pn3DQDb^(r1a<hk6$^@nyirX&6!es)q8XU!lQ`eQWmwjfUN*5g)PZ=h$<Lezj}UV30#Cv1-kOdOFG^!<vXiW4O8jO*m}ly3X=3@?LA_^*ItkU6Fz;^*)+9pF=}jaI){fU*OCwTYKI3AO=oh`mDVJ=jGT|rg!M>AN&j=Q=rkdjWMUMbvQ|yqRM=TVH;*6g^zUO@Ex`3Sn}VL#C`89HBlwQ6d6(%OxBKAdTkC>_^M?ONa3kPz>GYiCq?|v%c=jX#FUv>`aDU#7u&KZR2-OjnD|EW5C=GX`t9z%G&f|_C=XhzjXF^~FQwkoB<32hrRtD^KcOY086gef78PHxi-ML2^H~+A8|c-e;BtmhM>U@h0D^DqaS^4M@D}*FAH>zh)e*|k@u^XCD^j(ybln4I;vU*vcG=cvlQ1*d1k!eRmR&%)q|GA6&1JKhR4>35X7d=H*9p@|<;E<<IyHx;h0Y;lsyxIAOIwjL*O=X;J7}`SUnPnsG|LNiBC8Y;^$P0z!Z5UlX_getV;CA>%gDzZ(26ZH5Dx#fH)ebgYB0Nm1ypW&Vw(zG04&@P4M*kL-j%&}n6(*|o92NM(9`#%FjT%baWLb+lEAxS#C9jP!*v68Yds9t0|AF!9flkEv)>t;sWylMV=QZ-!*vXb6qC%u$mBP}nsYVVNXj&eaJCnilz+-TKdQyPPMg5rn7K$zrR(;cED6cDJ|LP{;l>Hqc4J+DV-^RIh1-#yZ4bH<<M6=o+`T^kvTeO_lA0{iK05sA$$_<2vSd%r5b7!ra}2|!_%bLdRxKjl>MtzJ(m!Lia9L#qW<BF>PgKj^G^B}iw>yN>euuD6!Vs%z;dPAAM5XTi@Qj_Q>v<{<-f`nVw{sPN#B1pbOh|G~y&d(i*z;Uniuh+KsH;`W<)ijs0QshFQ26?#Fr^HrLdlSeO`cU&z8<Zed^6e@_yvU_NWnTc#%!!Ml1I=B+!?`+Iil{G4+vN9YU23gpq(GsKaOUBYI#n2-!_<4WP<xTzSZYTSVc%c-ApoK6ooD_fBk)<nL<s7$ZQWG`$_38SrLr|cl@dqwkAlkJ{5$-JqFq=<w;9^%2ug}FN5OYJ;9Mh%e>l<ylY#9j%1)IHP>U}i`{FZh2KqX-L5SGF<Qe43(np32zoJhHzVK{U^sVta6pqYZ>B|d;dyZ&4lK0-&+xN|8x<qh;8{Jxv8s3SyRMZU1pdkC_x65v_Dxp4m`9DxyDpYfCm`^!oR*%_N|&~~h-kw~s`8GXJ4QdZmwZa%!>xG_x#L{O1~reB96pt>FW6;NM#V!G7o#%%1Nfh(EHP=3@xw4ao3E0D-A5US9I*F;ELUy%B7+)+D3{Fl9W^mAnRjGwwXmq44x;UtREnu#6gfmZ*%`%HXt~|pN^`Xmr-Eew1GYmzcRjR9kZ2?LW)Cp4%-zrvup`|KJke`L$+IMI)4)?wxF;6gulA%_wQc>jjDtLC!o8Y#H6FhL$-6f(hWq3UOF1I*K54;HQ$bc*+}avY8~kYr^R7L8I?AJ@XLRM#p8Lu<bPsG{*lE^G#@$kVairN}C%_KRR8Nju=a2dhAUsg^CzerhAAw?*ULb)#VU=+_$oK&5bYt$e0Y9Lo^=;`bj(F`RN7mkTUn}+f`$#6hIM7%ZT$K%1tGf!AMlcj@0pCX?6y{li5<O&h8xRgj1|DO%%(801QXk}zpHK#|A|jUfm`)-vZ{&K11HK0h__Tzd&gmBWpWN(d2sV&i7+Btjldd6vM(th0ZiXSA)5WYua4{{YKOKdu1)j7*<yywjmSmNG!d}*RuHM}<vW?u~>mE0HBElwBrQie5lMNc>NRs`($+~~Rep|%}p3a<um9VJe3DQ@h40@NH`oV&MsET+1NhI!tEQ5c4X=6;I$7I7#bO1=O0Q?2Ux4<Kt#|2pLeES@0lkbK>JBov~!d|rJfI;+D(k+b!vChgQqufWnK4l(-9<d*pL;ZHw%fY;s7)B4)6nrI<HeKN{+bS|3I5N62jp+Lok+{ma7PEY=2Px%0e7DV@<{6X;?a)~3cn$k?%Emp-)(I<$@<yZBn;iA)k@og9wz+oj-_1{VS?X7;&A$(60oBLA2DO%}X^Lq#L##l@6l~M>$$0<3!G8?>0Y12=WLwI|kjE?smV3B27|>WKAU$yRUfG7~b!>`8J#1@cj-5CMESt85=B37o^Y2P4U1N5H`})-ZZvE1e4Lv#7e|7W^Fhfs7Oqnkc#HmMZ_w&im1V}nza5R=9c6@dQPGeqVK~!P_FD+`GoBHU-6$Vgo0p6{``>1mJQ8tSOzSQGVm*v-b5g*<5@T4KwM`uP9;xtT2At)K`GFNJ^x=|-B>nGN^SjjXeupXsIqtm>kf>goxhK(Dw)LO|{({Nh&nL?=9u2hEq69L722dt=PS)_u9G~l7v_4K?~&i=mbC>xsIfm6$XA%-pcWRF6r?woWuN9-PPE;=&nlG|sRrrHsaRq+r%WJOzx{SU?Qbh`x2kgkO`G#F@R^<{2Kb>n+D$mF%Zw4ddF)dbp_LQtR0slmJ3L|W<q(xsDI(yS<BN=avfZP3BniB!}MoE3IDU7y?N?2k9KgvqNJyTlu0eo5ZIGe)h>qJKz>0NvlLKGIoVrU3ftVZ+bT@0paT>%AUwMd~2TWKgR#73NUDn9~Af9&XKqGAeG039p@S)6V7tCw;Vb^he(9X!B%9nXs7!s5|y17*R%hW^&lWus~vR3h~wi^l-vmfbEea4{J&TT<?Yhs@4OwA*hWRie?B#OPguKhxH(=hMxVW$;dOoc?7o^K5P(<pA!2MB^~pVV`|nehyjymX~c?TwWFRnB!8ym%j9l-KJ>Y+L|FLua*jmu@W4H6TVlBj)SS}CfNBhx(a_r)N;7W&%;_Br+F6)@VZ#w^G(<WBqs90nBAQ;_qfXgIlx;d?MEP1~*;`Hwa#5`;e|{38?<|!!wA}ID!O$JQ8mMO&YC6dP)Sw=x78KB~VbJ0@IaDk=&GOrH{!V)j7LT1d?DG9@$F|EZ>EfMHmL?lVI)@ngQBxR}tBStxYltLPav7_~Y{UgwUf^jg<kgtYhpgf>!sAyZ_?PHaa#biJrXq~0ur!F?JCHSaI4n+Fah{$5VG=-8l5^=-6|{-wWd{B%N62@0-1cCV?KheVDVD^<2$QC!r@Xd8IauWvOYPhqxDESCJR(ad7go=9r%J74cf9(?!Ml5G`=@OKnXyk0GDc@gZ$dYNU~$`H?ETc<U-{&&RTC#`<VmT>lP+|Ypfq>)CrVgr|CK@d7Wa2G6|G=sWuw3z;9>89m^bWU;AE1TM0W>s><!3#T8cmh@cCX&NdCEUYZ$FI_i(andBalrf!@S~<pppy0LMIbK{*yh6d((8V-iXNa0%#Crp2$kl3Z=OrcMn+WD<!0`qt1S-xjp25*!qamOB(mcQATxgYvcpKqkjGL^PVsIc>|zFn_Cb&L@RO`kIO4RkQ%9=e{&e6~DL%f%%s8fa3(^IwU3A74t&@&&9I|XI9DFXccsb9=_3}*)uu*w3?#IPnu1W!#;l(c|^84q)G!RZFdjNRk*}7#HiHve{b6M_UtWQGj6W^-n8jW`ayk)BSU|IpZ5<(@V7DHsy?rXA7w4FlFt7O+{w5hWVNMED+NYOhZ+aL(>&0jQ4{-sC)Cn&9YJ|<hZaB)X!V8&ZQl^ZzPwOm)_@BIzVbmz3%;~XLa^W_;dpYOa<4Zr2csrWGO*mxM@J!u3*6R`lyl@*9c<QlO$)icpiOr7<zctG$WM*&zr{oF>B=o!eh22|Vm9ujxLJ>Y662Q+3Y_&&e#d^gdlSb!96Rp8YfbJv&+u&Pio91>&;VemH}Y}+z^?Zr@Ihmz+C8HH^A5-1IXOvAjNR2giRPq%efz0g5ixy8_`>OI3=7lktEH@nxLL*=eo#0HXB&$7*~hq%6;uFz!mXYG;NPd9cjBPzGa<iYZZ;i02aml#v#ptSXU}$ScDO+SrEMSCuvifp*ZctA&4@;9a;jB?$dUHYu$OIYLJ7rSEA@Q>T7JGUiP?y*xeK8|RcDwy9}Q0_04!lF4ws881EgW=oWCSa>+z4~D#0o$tC>9d-rOn3ZPLj;*ji|<M%jJg=Znn|9piHt9g7l&5qCw1#SvxoIr;<yqN^IWGBi;ANnV8)YyygCVpy%(-JQtO)!BSrM*Mm{MHvwEVB&fL3Zp}W@>izDq*rtS+#XlS1fbmKh-C**rs5?S5NtzgKp^M){Q|wG8mQt-GD?~*u2<Xf?EMpXv`|%3d4&7;13rimXmUh00c2i-tSKD02O8F9af)-*M=Pg3PJQ$+<P+g2$Hb3tuH<+op4+)AMxJif0KGA8BY1o69{gx(ck7Dds#MwY6ku=S?sdV%+4>`Q0?w&w(Sf6nq^QrzAG!NOu*Eb0&$D4A>^Mwbhg*Q?0CA+>hkGK<ue<CjOCpihOnxWcgA1-B8r>x>!BMdA(=<w0y25jXavi+=aDL&o?uX@y<tD99?aA|Md{xrbxEAk~T$1-mb_WLIOgY~d&&5we!W3?FR1$?Y*}Tfvn;mN9X6LqPSF6<DF26Pydd(rh(X(#!D}`@%Y<HQ3E4f2~&RmftrMZqQtxxdt&2w=(F~7OV)vity6;Oh^|IQzR6!a6zZZI@EYV`%KT0PuR!2J=WMt6I{T=lmCz4*My?v%=%jdpY0Gq4UY7pqfK*<0UI(+?x9!!i)i*HOGqIgLu0FI6+#_j>-11fBWKTXe_O6qlcd=n4bPj<|CRTJGwmo1GxZf^UG2uc4@zb7dSA7OJKqLe8K06+n#P_nfrqA>QKBMOA`cRFoJ2!D0__C2Rfq1kc3G8_)=TX;;!YhWZA4FQkqJiMe%E85OagnDB=Y=*5u4B4s815KD%$IHi08m(%eQAzNk<Uh;dh<DfVYbMiv0JDXC-@9;PUj~da1(Q#VFAx|m4I=}dHDKZv<Ec=G(3fJeSc$Y@zhpxo-nQ~)`C|DI`{17D@4qPq#if$5GL`C!qv{ig-@&QAzcQ+#EAoym<xIk+pWtPw64g!o}<S92RQ@tle$4?4^pOkPl_}6+)Z*jwD>%5|7s%zC8L-n?B&GwGSRi+M|XQCMvhg9&|RZ^7OC3_`S)~$+NdCZg4Y7$6HZ_sblVr#PEyuPl3k~Js$W5?T-H&%^wC=62X9sHw$|52Vu*Yr&z;~%x`sQ)ju%~Bf!gMx@$2zI$s5roQwKN@c5A?d(v8jOZ3ciMB?282Zs#wjvzS%D~8mR$ytz3A^mZ^vnG`ug<hdiLr3<W$?f6?Zk&nqPNL9(jcBQN8X<@vtj?3Pa^g8qW+1w7Y@GqjgezJAjr^CG8Dy^?o}hb|1k=s=`8iI9d?lF!-|i{)1m)xq~JO*q2sp+jy@fbcPS;D>ij2ua_5Aq25!?VyrtWAGj#LE!x842gby$s*+sah2Ft|HN(;dqh6yWtkh|ZU+tinH3<Y_7xz63+4$<%8aC$DzK(Be-S#=7+_i?QpvP~dBq{wl>L+Bgid)hPdNV_b-lNRBkvGl3%!}*!<W+aP4=S%ABv3)nb{<v1!l<`!{XEvY;mXi7$rfcZ?(Fa0k?e@d8K6QLXP%K4>@WBN2^<HEC>hb-CAcWKtoXJl`U(7SZ43iWBUpf-h9BaHqT(f6#342>(V@DAr$uzPij#`rrWc;0q#*t;)DBQ_okuAudiMU}3r-xyYF7NfrFculyNfGbq0{hqq1Qhg75Fa6vgI>jVZ>V?VV>v`TupKuuc{1eKAZ2`ca<?o4S7X+eZE`*Hg?#pLEGuZ<gKESS|vmE8b!QCQI%gpXYzav_4ap>`%Ox_2k}ViRy{+cr+;tQtIqlDt888|G0Y>}?ey=8RbC0Qa}$IZzc%QiB*HBNw|$9Whhm)@dZe1_-Xnmy-}~dS8MJ%n0bYo|-vh0uG2sgvdI0M)C<ya<+$PNN@-C*`+In{zl`X6&AD2g5uxK5Zl+PE&OH`@90I|YV5Yb|4V*|k>(t3C@G~e~TljH;}C@}D4Fj63pHSHP>D9X*!NAphUw)-TukhEu?=5gy?5<QC^*Bt<Z4IKL=zhK;-$Y34x?NMx;)&_O$z};d(hRLwhV5S0tYAI9n0}IrUvE7D{*O|eZn~GSmwhA3@%MHaK>+?;u$kN$T);6ev8U*yg*mm}|BScBoLH8UTaV^8!J;>22nzl?NN4^xID+e7P<m3$G#niBn?T!|cejADeAT$h>(^r>6U1@v*`sTiKZi|PmelOcMo~h(erWHw0VIuvM>bN1^5@_)bIH0jsMKtrvAddM(D-Pz!rqvYBBw<WWrRFT~lLV73N-Z{b6%=vKecA?qEh8C~lMmU+@iqJS`Re1zDQo7dFDA#`*(|+^s#SjB<6ES_O)IUET0776*A1yPE>;Pq8u~>)$Xis2ZA{I@T)p0*kn^CrL|vDkeX#8Mi)fO^8O%PKDC{_C^d_#Utm|swN6|&utahJQ(;3{_JO=AHzAN1TtvO`7w_$C{*7<{_gDDg~Nk(kO<rzTQ)hSuBQAf&mcrV~7-!&mLw!^^v1)VCmhxs9Z(1lTots$ERm#4y06m(gJOwGV{9D(h~kn@HHJk@gz$&CEm{)M>B14M|a_$^TthT9uWQN@sDnEjDF(lqeEm$#o2mEmNS4{V(iab?kq(Pq&)3RYFrv$RfmDXttcH#obnIu^rYCv@Hv2Aa`wyFNedtSP()7O`s!3x{NFStFc(`T^eI05}#JOC4{Liv-E2tqT3EUe8$>t{TtM-rIFbAG+7D1jB-FBG)4p-XPF9XkCBT(niMcAnm}Bmm*NN8MMHd*3Hh>_PhFSp(Z9C@>=~W!PshVtu3-$)akMr*`%{ZuPEGAOI4=unM)^`=`<I(G)Wx9{30p!9eg!^^$1+tYXkj7PB6I)mm;#OT&DV%Mwl6daP+-Z)Q%5|?MY*qJ@mTcrpu>+foFoXs!$vI<tmji-RqMh29*8tE)4MZD5$($US+q1;?Ffx$^s0~>MM<_Ww}ObIFzo_o1JzG$YIekuC)7S>g5A{!g?}dwTM7EDA`2xDn5K@A)OtdWJ&kVhf(Fn$&@%(i#K3>nWyvpW``cYoKS7>7V$gTARH0xV-qUezOD+3|FC~F{-fw=Hzv%xC08|!k}C&gH2SV5wasBfzi_*OfB7M&_CHtR{?ArO$&o+#xd-@JKE|-7l|YWu3GJ9O4fGJI(-ljOAx4gyD5@y$L*8ehI=y9$Qs}{nDXyX-;R$?<4LFK>;WQxwM@9tXPD?k=uSTvU!41=zf`NQ=voj>lX+#tLwAD~m!zuEr@8Bz+Z2pRp0NdfS+zRBcl8SGRJ%ck^Tk=4+w$;_^8>nqkgl5{~q$$FQhmoeHNQ>5qp0G=UV+(+Y-%(I8;9|6<*S2`2ixt6&`=Ok3U+4Tj7EG+FtY_>PG?CZt%-3;K*+bx_x`kh-^<$^Z&|H#%NG&4|rlWU)G$Ml9Ch?AEVz7n?`~tLy`$_=l1hE^BycnP)KzBe23avSXi{*9gb)g8Yqh?b_p)E$+&=#1Xm^_a+o@BbM{*@c)w}!<d2*I|s)otnwqq?8K-CE%bZpkylTt_}iQlE%{o&mMG1CmD3eZHCz)Xb-z3h~BW3d2q;wgkf*y`dl|H-Y*aG<3YgG=6;bFgN{yUP_<o8R5u_XbCbx;F(VG)Eih};YJh~iGqg{7CtU>p7V}?F<Lm3)C=uUkO?(l(_mR46v1!pF2@L_Q5q^8E{lL3Dg7*c5jd4Fc#mcqC|e?!p*^J;uEw<P%ICIu@ciuPV?pO?O~WMsQEtM)-z`ny3lxl0hd=9C5?mjdP=R<@@NBj?0EC80d;++=gaOp11yS2bAS&UnvIewxV4ClU^ff^61a6Ne_OD(vIy7Ld!@2Xszc0lC7Ak`x<?u6%%RKQnhT6C&xX2eZ)76su$Zs&8;`@)<CC9JwI852>WNCG33;<Y~NDJySOICuVg{q+uPN&}F6+aj(9`o0HPp2;@W5-fK9Sy+T3XPujIhuCJ5W@?0rc>jt1vPHo&rqsz+^yIF8Xb!Mo5yMRR@@+Awc`flNYTMv+6kp!R`=)&FEAZ?k=&HymLxPTA;IQBjA+OTo0gZTmW1levFWqiOeG6NZJxh6T^fO6#cFjO?U%j9hT3j@b&V@ys8k7I9<|2R#5TYGKy+0&!_Bf#I1k`<xb$1vCP;o@^rN5gakcm*j_-;1rS7HwTx~sBk5}N19cH)8&?cMBxHOv0@SOi_R{OV&d&phUvI5V1uQt?Xe(2{F%1^}~J*QX(__-pQis_0?IQ588on{y13Q@8>mcW9-6r$1*;UO@#=(OGSB5I%)QIhlHKGlNuG3iKc1_Ev2mrSTm5N<K1C$qoPi<z>j%9f*54%psiDMsK}4ElnO+GX&6J_^AZ$K6fBDN`|Bc3v%@EuN_gi?Cc|s|4>iLbsA&Z&E=3E<0Cwj(gA0-!KbSxcL%=Jd?ArgG2B{0(^56G<^obF<4~Sv6l0VS*8DHLdX4a;eROKYT@%YQD(WmA@Bj8XDjd+bPI}JvDF2C2aiqQA~dmzETki)U^wC(xYKd#wo8QAei5LkY07NC%G<LV)OSJAq=II<;<pk%v$a~%^`t&@Rx$QKf8`W^Zu1>vtpPe4i)z=xDRJa#Q)#r82_^&ra&u?#{l^jfzit$`UfF5A*s8&`>BF`8d0b-5BGld<^4f0RLRCN9@P}wMt?eOxZ0tAgc)|(OTtthBBvUjbDb=T1td@5a$xHC$Yfgm?a2*G;x-ou0<PaK%kT{6K;RrZzcQ~lWa?L%f&uj?%IEJqBYOe3*4PsL`IB(K=9hc}&oYT;izzC(p;LFE6XVMyk>@S}jj7NphdInUzj|x1XqG@+YH?0Oe)WB-8s$lf6gHcjmg<QsAm_)J<%b-=`i9YA87GgPvR^OC$?w3?<(|N(pqI*Bs2t8C%f~^RofIBDhB(1UI*^NR2BOYJAiFamV59?f<_uLkb1KuON3a^OJNho=0Z5iQ#<tV|c#e-yp{*ZXX=il*_gm|#LPRD587Wd@nq&g77hEDy^VU4Lv*Uroy=nF?kiQD44?chO->DZw&6;t!uJLmw#lrMc0<}e?>`;X^222ahq)^wm^YH3vn%M})!MRVk)VNdZTTJ<O{2JS%<r0c$1unhb}UULYG;lMGjB8{*3d(j#=q$ttS-sRYSW$wNjp2F*zqEM^TEJ60ByKvz#y=Jei0%W!VpB4BQbby!{Z-hU++n%H+ZjGS%vk^*wgZHKj(2U|7*WK4%sb-70rlU9X;Cb7(jqYpS!K{X4oA)j@r-Rf(L5@81<J2d3oceH%)4Z@!n_+Et_bn_n9>?W3l5onZD!kre`SIVc7}nG'
def embedded_sources():
    return json.loads(zlib.decompress(base64.b85decode(_PAYLOAD)).decode("utf-8"))

# TD Text DAT Run Script does not use __name__ == "__main__".
try:
    import td as _td
except ImportError:
    pass  # ordinary Python may inspect/compile this artifact
else:
    build(embedded_sources())
