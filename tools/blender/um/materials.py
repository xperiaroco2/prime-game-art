"""Flat material colours: the packs have no textures, only material colours. Workbench renders the viewport colour
(diffuse_color) and the glTF exporter the Principled BSDF base colour; both are kept equal."""

from .util import base_name


def set_color(mat, rgb):
    mat.diffuse_color = (rgb[0], rgb[1], rgb[2], 1.0)
    if mat.node_tree:
        for n in mat.node_tree.nodes:
            if n.type == "BSDF_PRINCIPLED":
                n.inputs["Base Color"].default_value = (rgb[0], rgb[1], rgb[2], 1.0)


def color_of(spec, parts):
    """A colour spec is [r, g, b] or {"from_part": role, "material": name}: that part's material colour."""
    if isinstance(spec, dict):
        for slot in parts[spec["from_part"]].material_slots:
            if slot.material and base_name(slot.material.name) == spec["material"]:
                return [round(x, 4) for x in slot.material.diffuse_color[:3]]
        raise KeyError("no material %s on %s" % (spec["material"], spec["from_part"]))
    return list(spec)


def principled(mat):
    """The material's Principled BSDF, made (with an output) when it has none."""
    if mat.node_tree is None:
        mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = next((n for n in nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        bsdf = nodes.new("ShaderNodeBsdfPrincipled")
        out = next((n for n in nodes if n.type == "OUTPUT_MATERIAL"), None) or nodes.new("ShaderNodeOutputMaterial")
        mat.node_tree.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return bsdf


def sync_principled(mat, scripted):
    """Principled base colour := the viewport colour (what Workbench showed). For our scripted face materials (made
    with viewport settings only) roughness and metallic follow too; the packs' own materials keep theirs.
    Returns the largest colour difference that was corrected."""
    if mat.get("look") in ("clay", "baked"):  # the clay look (um/clay.py): a procedural or textured base colour
        return 0.0
    if mat.get("base_from") == "vertex_colour":  # the face kit's eyes (clayface/adapter.eye_material)
        return 0.0
    bsdf = principled(mat)
    base = bsdf.inputs["Base Color"]
    if base.is_linked:
        raise ValueError(f"material {mat.name}: its base colour is driven by nodes; the packs have flat colours only")
    before = max(abs(a - b) for a, b in zip(base.default_value[:3], mat.diffuse_color[:3]))
    base.default_value = tuple(mat.diffuse_color[:3]) + (1.0,)
    if scripted:
        bsdf.inputs["Roughness"].default_value = mat.roughness
        bsdf.inputs["Metallic"].default_value = mat.metallic
    return before
