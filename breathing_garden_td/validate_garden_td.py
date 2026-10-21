"""Run inside TD: op('/project1/garden/validate_garden').module.validate()."""
import json


def validate(path="/project1/garden", emit=True):
    garden = op(path)
    checks = []
    def check(name, passed, detail=""):
        checks.append({"check":name,"ok":bool(passed),"detail":str(detail)})
    if garden is None:
        check("garden",False,path)
        return {"ok":False,"checks":checks}
    required = ("input_test","input_live","switch_tracking","null_tracking",
                "garden_engine","garden_runtime","garden_controls","frame_execute",
                "geo_growth/branches_sop","geo_growth/branches_sop_callbacks",
                "line_growth","cam1","render1","bloom1","out1","reset_controls")
    for name in required:
        check("node:"+name,garden.op(name) is not None)
    if not all(c["ok"] for c in checks):
        result = {"ok":False,"checks":checks}
    else:
        sop = garden.op("geo_growth/branches_sop")
        render = garden.op("render1")
        output = garden.op("out1")
        sop.cook(force=True)
        output.cook(force=True)
        channels = {c.name for c in garden.op("null_tracking").chans()}
        expected = set(garden.op("garden_engine").module.CHANNELS)
        check("tracking channels",expected <= channels,sorted(channels))
        geo = garden.op("geo_growth")
        material_par = getattr(geo.par,"material",None) or getattr(geo.par,"mat",None)
        check("material",material_par is not None and material_par.eval() == garden.op("line_growth"))
        check("Cd RGBA",sop.pointAttribs["Cd"] is not None)
        mat = garden.op("line_growth")
        check("Line MAT uses SOP color",mat.par.linecoloratt.eval() == garden.fetch("gpu_color_attribute","Cd"),
              "SOP Cd -> GPU " + mat.par.linecoloratt.eval())
        check("straight point RGB",mat.par.pointcolorpremult.eval()=="alreadypremult")
        check("no shader alpha multiplication",not bool(mat.par.postmultalpha))
        check("straight alpha blend",mat.par.srcblend.eval()=="sa" and mat.par.destblend.eval()=="omsa")
        check("alpha blending",bool(mat.par.blending))
        check("no depth writing",not bool(mat.par.depthwriting))
        check("camera",render.par.camera.eval() == garden.op("cam1"))
        check("orthographic",garden.op("cam1").par.projection.eval() == "ortho")
        check("ortho width",abs(float(garden.op("cam1").par.orthowidth)-2)<1e-6)
        check("geometry flags",sop.render and sop.display)
        check("SOP output",sop.numPoints>0,"{} points, {} primitives".format(sop.numPoints,sop.numPrims))
        check("resolution",output.width==1280 and output.height==720,(output.width,output.height))
        check("render chain",output.inputs[0]==garden.op("bloom1") and garden.op("bloom1").inputs[0]==render)
        for node in garden.findChildren():
            errors = node.errors()
            if errors:
                check("operator errors:"+node.path,False,errors)
        runtime_error = garden.fetch("last_runtime_error","")
        check("frame callback",not runtime_error,runtime_error)
        result = {"ok":all(c["ok"] for c in checks),"checks":checks,
                  "metrics":garden.fetch("metrics",{}),"td_build":str(app.build)}
    if emit:
        garden.op("diagnostics").text = json.dumps(result,ensure_ascii=False,indent=2)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    return result


if __name__ == "__main__":
    validate()
