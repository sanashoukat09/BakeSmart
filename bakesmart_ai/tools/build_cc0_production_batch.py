"""Build review-only BakeSmart GLBs from vetted CC0 model sources.

Run with Blender. This is deterministic local asset processing, not AI.
"""
from __future__ import annotations
import argparse, csv, json, math, shutil, sys, traceback, zipfile
from pathlib import Path
import bpy
from mathutils import Matrix, Vector

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

def duplicate_group(objs,prefix,placements):
    originals=list(objs); output=list(originals)
    for copy_index,(dx,dy,dz,rotation_deg,scale) in enumerate(placements,1):
        transform=Matrix.Translation(Vector((dx,dy,dz))) @ Matrix.Rotation(math.radians(rotation_deg),4,"Z") @ Matrix.Scale(scale,4)
        for object_index,source in enumerate(originals,1):
            duplicate=source.copy(); duplicate.data=source.data.copy(); duplicate.name=f"{prefix}_{copy_index:02d}_{object_index:02d}"
            for collection in source.users_collection[:1]: collection.objects.link(duplicate)
            duplicate.matrix_world=transform @ source.matrix_world; output.append(duplicate)
    bpy.context.view_layer.update(); return output

def mat(name,color,metal=0.0,rough=0.45):
    m=bpy.data.materials.new(name); m.use_nodes=True; b=next(n for n in m.node_tree.nodes if n.type=="BSDF_PRINCIPLED"); b.inputs["Base Color"].default_value=color; b.inputs["Metallic"].default_value=metal; b.inputs["Roughness"].default_value=rough; return m

def cube(name,dim,loc,m):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc); o=bpy.context.active_object; o.name=name; o.dimensions=dim; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); o.data.materials.append(m); return o

def build(row):
    kind=row["builder"]
    if kind=="low_floral_centerpiece":
        vase=import_source(row["primary_source_id"],"CC0_Vase"); greenery=import_source(row["secondary_source_id"],"CC0_Greenery"); blossoms=import_source(row["tertiary_source_id"],"CC0_Gazania")
        helper=mat("BS_CeramicHelper",(0.92,0.89,0.82,1)); fit_exact(vase,.16,.16,.18,0.0)
        fit_exact(greenery,.18,.18,.075,.155)
        duplicate_group(greenery,"BS_GreeneryFiller",((.075,0,-.005,35,.82),(-.075,0,-.005,-35,.82),(0,.075,-.008,90,.78),(0,-.075,-.008,-90,.78)))
        fit_exact(blossoms,.13,.13,.085,.19)
        duplicate_group(blossoms,"BS_BlossomCrown",((.09,0,-.005,35,.92),(-.09,0,-.005,-35,.92),(0,.09,-.01,80,.88),(0,-.09,-.01,-80,.88),(.065,.065,.005,125,.78),(-.065,.065,.005,-125,.78),(.065,-.065,.0,160,.78),(-.065,-.065,.0,-160,.78)))
        return helper
    if kind=="marigold_brass_cluster":
        brass=import_source(row["primary_source_id"],"CC0_Brass"); foliage=import_source(row["secondary_source_id"],"CC0_FoliageSupport"); blossoms=import_source(row["tertiary_source_id"],"CC0_Gazania")
        helper=mat("BS_BrassHelper",(0.55,0.30,0.06,1),.72,.28); fit_exact(brass,.32,.32,.32,0.0)
        fit_exact(foliage,.18,.18,.55,.28)
        duplicate_group(foliage,"BS_FoliageSupport",((.14,0,-.02,20,.78),(-.14,0,-.03,-22,.72),(0,.14,-.04,70,.68),(0,-.14,-.04,-70,.68)))
        fit_exact(blossoms,.18,.18,.18,.28)
        duplicate_group(blossoms,"BS_MarigoldLook",((.17,0,.00,28,.90),(-.17,0,.00,-28,.90),(0,.17,-.01,78,.88),(0,-.17,-.01,-78,.88),(.12,.12,.10,118,.78),(-.12,.12,.12,-118,.78),(.12,-.12,.09,158,.78),(-.12,-.12,.11,-158,.78),(0,0,.30,42,.72),(0.08,0,.42,-18,.60),(-.08,.02,.50,18,.54)))
        return helper
    if kind=="mirror_welcome_sign":
        mirror=import_source(row["primary_source_id"],"CC0_Mirror"); stand=mat("BS_Stand",(0.68,0.52,0.20,1),.65,.30); plaque=mat("BS_WelcomePlaque",(0.82,0.78,0.70,1),.08,.32)
        fit_exact(mirror,.70,.035,1.34,.16); cube("BS_FootL",(.16,.05,.025),(-.27,0,.0125),stand); cube("BS_FootR",(.16,.05,.025),(.27,0,.0125),stand); cube("BS_BracketL",(.028,.04,.16),(-.30,0,.09),stand); cube("BS_BracketR",(.028,.04,.16),(.30,0,.09),stand); cube("BS_ReplaceableWelcomePlaque",(.42,.014,.18),(0,-.024,.98),plaque); return stand
    raise RuntimeError(f"unknown builder {kind}")

def triangles(objs):
    total=0
    for o in objs: o.data.calc_loop_triangles(); total += len(o.data.loop_triangles)
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

def source_ids(row):
    return [row.get(k,"") for k in ("primary_source_id","secondary_source_id","tertiary_source_id") if row.get(k,"")]

def export(row,mrow,helper_mat):
    expected=(float(mrow["width_m"]),float(mrow["depth_m"]),float(mrow["height_m"])); meshes=[o for o in bpy.context.scene.objects if o.type=="MESH"]; lo,hi=bounds(meshes); c=(lo+hi)/2; move(meshes,Vector((-c.x,-c.y,-lo.z)))
    budget=int(mrow["lod0_triangle_budget"]); decimate(meshes,budget); bpy.context.view_layer.update(); lo,hi=bounds(meshes); actual=hi-lo
    for i,label in enumerate(("width","depth","height")):
        if actual[i] > expected[i] + .02: raise RuntimeError(f"{label} {actual[i]:.4f} exceeds placement envelope {expected[i]:.4f}")
        if actual[i] < expected[i] * .60: raise RuntimeError(f"{label} {actual[i]:.4f} is grossly undersized for placement envelope {expected[i]:.4f}")
    tc=triangles(meshes)
    if tc>budget: raise RuntimeError(f"triangle budget exceeded: {tc}")
    root=bpy.data.objects.new("BS_ROOT",None); bpy.context.collection.objects.link(root)
    for o in meshes: o.parent=root
    ids=source_ids(row); root["bakesmart_asset_id"]=mrow["asset_id"]; root["bakesmart_catalog_id"]=mrow["catalog_id"]; root["bakesmart_units"]="metres"; root["bakesmart_dimensions_m"]=list(expected); root["bakesmart_anchor_type"]=mrow["anchor_type"]; root["bakesmart_scaling_policy"]=mrow["scaling_policy"]; root["bakesmart_manifest_version"]="production-assets-v1"; root["bakesmart_review_only"]=True; root["bakesmart_source_license"]="cc0_confirmed"; root["bakesmart_source_ids"]=ids
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
