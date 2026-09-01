"""Build review-only BakeSmart GLBs from vetted CC0 model sources.

Run with Blender. This is deterministic local asset processing, not AI.
"""
from __future__ import annotations
import argparse, csv, json, math, shutil, sys, traceback, zipfile
from pathlib import Path
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "data/production_assets_v1/production_batch1_plan.csv"
MANIFEST = ROOT / "data/production_assets_v1/asset_manifest.csv"
RAW = ROOT / "assets/third_party_cc0/raw"
WORK = ROOT / "assets/third_party_cc0/working"
REPORT = ROOT / "data/production_assets_v1/production_candidate_build_report.json"


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser(); p.add_argument("--plan", type=Path, default=PLAN); p.add_argument("--asset-id", action="append"); p.add_argument("--report", type=Path, default=REPORT); return p.parse_args(argv)

def rows(path):
    with path.open(encoding="utf-8", newline="") as f: return list(csv.DictReader(f))

def clear():
    bpy.ops.object.select_all(action="SELECT"); bpy.ops.object.delete(use_global=False)

def source_file(source_id):
    if not source_id or not source_id.strip(): raise RuntimeError("source id must be non-empty")
    folder = RAW / source_id
    if not folder.is_dir(): raise RuntimeError(f"missing downloaded source: {folder}")
    archives = sorted(folder.glob("*.zip")); search = folder
    if archives:
        search = WORK / source_id; shutil.rmtree(search, ignore_errors=True); search.mkdir(parents=True)
        with zipfile.ZipFile(archives[0]) as z: z.extractall(search)
    found = sorted(search.rglob("*.glb")) + sorted(search.rglob("*.gltf"))
    if not found: raise RuntimeError(f"no glTF/GLB in {folder}")
    return found[0]

def import_source(source_id, prefix):
    before = set(bpy.context.scene.objects); bpy.ops.import_scene.gltf(filepath=str(source_file(source_id)))
    imported = [o for o in bpy.context.scene.objects if o not in before]
    for o in list(imported):
        if o.type in {"CAMERA","LIGHT"}: bpy.data.objects.remove(o, do_unlink=True); imported.remove(o)
    meshes = [o for o in imported if o.type == "MESH"]
    if not meshes: raise RuntimeError(f"{source_id} has no mesh")
    for i,o in enumerate(meshes,1):
        world=o.matrix_world.copy(); o.parent=None; o.matrix_world=world; o.name=f"{prefix}_{i:02d}"
    for o in list(imported):
        if o.type == "EMPTY" and o.users_collection: bpy.data.objects.remove(o, do_unlink=True)
    bpy.context.view_layer.update(); return meshes

def bounds(objs):
    pts=[o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    lo=Vector(tuple(min(p[i] for p in pts) for i in range(3))); hi=Vector(tuple(max(p[i] for p in pts) for i in range(3))); return lo,hi

def move(objs,d):
    for o in objs: o.location += d

def fit_exact(objs,w,d,h,z):
    lo,hi=bounds(objs); c=(lo+hi)/2; move(objs,Vector((-c.x,-c.y,-lo.z))); lo,hi=bounds(objs); dim=hi-lo
    sx,sy,sz=w/max(dim.x,1e-6),d/max(dim.y,1e-6),h/max(dim.z,1e-6)
    for o in objs: o.location=Vector((o.location.x*sx,o.location.y*sy,o.location.z*sz)); o.scale=Vector((o.scale.x*sx,o.scale.y*sy,o.scale.z*sz))
    bpy.context.view_layer.update(); lo,hi=bounds(objs); c=(lo+hi)/2; move(objs,Vector((-c.x,-c.y,z-lo.z)))

def mat(name,color,metal=0.0,rough=0.45):
    m=bpy.data.materials.new(name); m.use_nodes=True; b=next(n for n in m.node_tree.nodes if n.type=="BSDF_PRINCIPLED"); b.inputs["Base Color"].default_value=color; b.inputs["Metallic"].default_value=metal; b.inputs["Roughness"].default_value=rough; return m

def cube(name,dim,loc,m):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc); o=bpy.context.active_object; o.name=name; o.dimensions=dim; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); o.data.materials.append(m); return o

def ico(name,loc,scale,m):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=1.0,location=loc); o=bpy.context.object; o.name=name; o.scale=scale; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); o.data.materials.append(m); return o

def cylinder_between(name,start,end,radius,m,vertices=8):
    a=Vector(start); b=Vector(end); delta=b-a; length=delta.length
    if length <= 1e-6: return None
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=radius,depth=length,location=(a+b)*.5)
    o=bpy.context.object; o.name=name; o.rotation_euler=delta.to_track_quat("Z","Y").to_euler(); o.data.materials.append(m); return o

def add_leaf(name,loc,angle,m,length=.035,width=.013):
    o=ico(name,loc,(length,width,.0045),m); o.rotation_euler[2]=angle; return o

def add_daisy(name,center,petal,core,petal_radius=.024):
    c=Vector(center); ico(name+"_Core",c,(.010,.010,.007),core)
    for i in range(8):
        a=2*math.pi*i/8; p=c+Vector((math.cos(a)*petal_radius*.62,math.sin(a)*petal_radius*.62,0))
        o=ico(f"{name}_Petal_{i:02d}",p,(petal_radius*.55,petal_radius*.24,.0045),petal); o.rotation_euler[2]=a

def add_marigold(name,center,orange,gold,r=.027):
    c=Vector(center); ico(name+"_Core",c,(r*.62,r*.62,r*.55),gold)
    for i in range(12):
        a=2*math.pi*i/12; ring=.012 if i%2==0 else .018; z=.004 if i%3 else -.003
        ico(f"{name}_Floret_{i:02d}",c+Vector((math.cos(a)*ring,math.sin(a)*ring,z)),(r*.46,r*.42,r*.40),orange if i%2 else gold)

def add_text_mesh(body,name,location,material,target_width,size=.20):
    bpy.ops.object.text_add(location=location,rotation=(math.radians(90),0.0,0.0)); obj=bpy.context.object; obj.name=name; obj.data.body=body; obj.data.align_x="CENTER"; obj.data.align_y="CENTER"; obj.data.size=size; obj.data.extrude=.003; obj.data.bevel_depth=.001
    bpy.context.view_layer.update()
    if obj.dimensions.x>1e-6: obj.scale*=target_width/obj.dimensions.x
    bpy.context.view_layer.objects.active=obj; obj.select_set(True); bpy.ops.object.convert(target="MESH"); obj=bpy.context.object; obj.data.materials.append(material); return obj

def build_low_floral(row):
    vase=import_source(row["primary_source_id"],"CC0_Vase"); fit_exact(vase,.15,.15,.16,0.0)
    green=mat("BS_StemGreen",(.10,.23,.08,1),0,.68); blush=mat("BS_BlushPetal",(.78,.38,.34,1),0,.55); cream=mat("BS_CreamPetal",(.94,.84,.68,1),0,.58); gold=mat("BS_FlowerCore",(.78,.48,.12,1),.08,.48)
    heads=[(-.12,-.04,.235),(-.09,.075,.255),(-.055,-.105,.265),(-.02,.02,.285),(.025,-.085,.255),(.055,.085,.275),(.095,-.015,.245),(.12,.055,.23),(-.115,.11,.225),(.105,-.11,.225),(-.04,.135,.235),(.035,-.135,.245)]
    for i,end in enumerate(heads):
        base=(end[0]*.18,end[1]*.18,.145); cylinder_between(f"BS_Stem_{i:02d}",base,end,.0028,green)
        mid=((base[0]+end[0])*.55,(base[1]+end[1])*.55,(base[2]+end[2])*.55); add_leaf(f"BS_Leaf_{i:02d}",mid,math.atan2(end[1],end[0])+.65,green)
        add_daisy(f"BS_Flower_{i:02d}",end,blush if i%3 else cream,gold,.025 if i%2 else .022)
    return mat("BS_CeramicHelper",(.92,.89,.82,1))

def build_marigold(row):
    brass=import_source(row["primary_source_id"],"CC0_Brass"); fit_exact(brass,.34,.34,.34,0.0)
    green=mat("BS_MarigoldStem",(.08,.18,.055,1),0,.72); orange=mat("BS_MarigoldOrange",(.95,.28,.035,1),0,.58); saffron=mat("BS_MarigoldSaffron",(1.0,.53,.045,1),0,.56)
    heads=[]
    for ring,count,z0 in ((.24,12,.66),(.16,10,.80),(.075,6,.93)):
        for i in range(count):
            a=2*math.pi*i/count + (0.18 if count==10 else 0); z=z0 + .035*math.sin(i*1.7); heads.append((math.cos(a)*ring,math.sin(a)*ring,z))
    for i,end in enumerate(heads):
        base=(end[0]*.22,end[1]*.22,.30); cylinder_between(f"BS_MehndiStem_{i:02d}",base,end,.0038,green)
        if i%2==0:
            mid=((base[0]+end[0])*.62,(base[1]+end[1])*.62,(base[2]+end[2])*.58); add_leaf(f"BS_MehndiLeaf_{i:02d}",mid,math.atan2(end[1],end[0])+.55,green,.050,.016)
        add_marigold(f"BS_Marigold_{i:02d}",end,orange,saffron,.030 if i<12 else .027)
    return mat("BS_BrassHelper",(.55,.30,.06,1),.72,.28)

def build(row):
    kind=row["builder"]
    if kind=="low_floral_centerpiece": return build_low_floral(row)
    if kind=="marigold_brass_cluster": return build_marigold(row)
    if kind=="mirror_welcome_sign":
        mirror=import_source(row["primary_source_id"],"CC0_Mirror"); stand=mat("BS_Stand",(.68,.52,.20,1),.65,.30); lettering=mat("BS_WelcomeLettering",(.88,.71,.28,1),.45,.28)
        fit_exact(mirror,.70,.035,1.34,.16); cube("BS_FootL",(.16,.05,.025),(-.27,0,.0125),stand); cube("BS_FootR",(.16,.05,.025),(.27,0,.0125),stand); cube("BS_BracketL",(.028,.04,.16),(-.30,0,.09),stand); cube("BS_BracketR",(.028,.04,.16),(.30,0,.09),stand)
        add_text_mesh("Welcome","BS_WelcomeText",(0,-.023,.99),lettering,.36,.18); add_text_mesh("Celebrate with us","BS_SubtitleText",(0,-.023,.86),lettering,.30,.08); return stand
    raise RuntimeError(f"unknown builder {kind}")

def triangles(objs):
    total=0
    for o in objs: o.data.calc_loop_triangles(); total+=len(o.data.loop_triangles)
    return total

def decimate(objs,budget):
    for _ in range(3):
        total=triangles(objs)
        if total<=budget: return
        ratio=max(.05,min(.92,budget/max(total,1)*.84))
        for o in objs:
            o.data.calc_loop_triangles()
            if len(o.data.loop_triangles)<100: continue
            mod=o.modifiers.new("BS_LOD0","DECIMATE"); mod.ratio=ratio; bpy.context.view_layer.objects.active=o; o.select_set(True); bpy.ops.object.modifier_apply(modifier=mod.name); o.select_set(False)
        bpy.context.view_layer.update()
    if triangles(objs)>budget: raise RuntimeError(f"decimation could not meet triangle budget {budget}")

def source_ids(row): return [row.get(k,"") for k in ("primary_source_id","secondary_source_id","tertiary_source_id") if row.get(k,"")]

def export(row,mrow,helper_mat):
    expected=(float(mrow["width_m"]),float(mrow["depth_m"]),float(mrow["height_m"])); meshes=[o for o in bpy.context.scene.objects if o.type=="MESH"]; lo,hi=bounds(meshes); c=(lo+hi)/2; move(meshes,Vector((-c.x,-c.y,-lo.z)))
    budget=int(mrow["lod0_triangle_budget"]); decimate(meshes,budget); bpy.context.view_layer.update(); lo,hi=bounds(meshes); actual=hi-lo
    for i,label in enumerate(("width","depth","height")):
        if actual[i]>expected[i]+.02: raise RuntimeError(f"{label} {actual[i]:.4f} exceeds placement envelope {expected[i]:.4f}")
        if actual[i]<expected[i]*.60: raise RuntimeError(f"{label} {actual[i]:.4f} is grossly undersized for placement envelope {expected[i]:.4f}")
    tc=triangles(meshes)
    if tc>budget: raise RuntimeError(f"triangle budget exceeded: {tc}")
    root=bpy.data.objects.new("BS_ROOT",None); bpy.context.collection.objects.link(root)
    for o in meshes: o.parent=root
    ids=source_ids(row); root["bakesmart_asset_id"]=mrow["asset_id"]; root["bakesmart_catalog_id"]=mrow["catalog_id"]; root["bakesmart_units"]="metres"; root["bakesmart_dimensions_m"]=list(expected); root["bakesmart_anchor_type"]=mrow["anchor_type"]; root["bakesmart_scaling_policy"]=mrow["scaling_policy"]; root["bakesmart_manifest_version"]="production-assets-v1"; root["bakesmart_review_only"]=True; root["bakesmart_source_license"]="cc0_confirmed"; root["bakesmart_source_ids"]=ids; root["bakesmart_local_authored_geometry"]=row["builder"] in {"low_floral_centerpiece","marigold_brass_cluster"}
    out=ROOT/mrow["glb_path"]; out.parent.mkdir(parents=True,exist_ok=True); bpy.ops.export_scene.gltf(filepath=str(out),export_format="GLB",export_extras=True,export_apply=True,export_yup=True,export_materials="EXPORT")
    return {"asset_id":row["asset_id"],"output":str(out.relative_to(ROOT)),"source_ids":ids,"source_license_status":"cc0_confirmed","redistribution_allowed":True,"true_dimensions_m":[round(float(v),4) for v in expected],"visible_mesh_bounds_m":[round(float(v),4) for v in actual],"triangle_count":tc,"status":"built_for_geometry_review"}

def main():
    a=args(); plan=rows(a.plan); manifest={r["asset_id"]:r for r in rows(MANIFEST)}; chosen=set(a.asset_id or []); result=[]
    for row in plan:
        if chosen and row["asset_id"] not in chosen: continue
        if row["source_license_status"]!="cc0_confirmed" or row["redistribution_allowed"]!="true": raise RuntimeError(f"rights gate failed {row['asset_id']}")
        clear(); result.append(export(row,manifest[row["asset_id"]],build(row))); print(json.dumps(result[-1],indent=2))
    if not result: raise RuntimeError("no candidates selected")
    a.report.parent.mkdir(parents=True,exist_ok=True); a.report.write_text(json.dumps({"report_version":"production-candidate-build-v1","review_only":True,"production_ready":False,"assets":result,"note":"Human visual review required before production_ready."},indent=2)+"\n",encoding="utf-8")

if __name__=="__main__":
    try: main()
    except Exception:
        traceback.print_exc(); raise SystemExit(1)
