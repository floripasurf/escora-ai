# Escora.AI Parser Improvements Research

## 1. Current Limitations

### What the parser handles today

- **LINE entities**: Only strictly horizontal (dy < 0.01) and vertical (dx < 0.01) lines are extracted as segments. Diagonal lines and arcs are silently dropped.
- **LWPOLYLINE / POLYLINE**: Stored as PolylineEntity, but only 2-point polylines are decomposed into H/V segments. Multi-segment polylines (common in real drawings for beam outlines) are not broken into their constituent line segments.
- **SOLID entities**: Used for pillar detection (bounding-box approach). Works for filled rectangular columns but misses hollow or complex shapes.
- **CIRCLE entities**: Used for circular column detection with cluster filtering.
- **TEXT / MTEXT**: Extracted for annotation-based classification.

### What the parser misses

| Entity Type | Impact | Priority |
|---|---|---|
| **INSERT (block references)** | Many CAD files store pillars, beams, and standard details as blocks. These are completely invisible to the parser. | Critical |
| **HATCH** | Engineers often hatch slab areas, concrete sections, and fill patterns. Ignored entirely. | High |
| **DIMENSION** | Section dimensions (e.g., "14x50") embedded as DIMENSION entities are not read. Only TEXT/MTEXT dimensions are captured. | High |
| **ARC / ELLIPSE** | Curved beams, rounded slab edges, and curved walls are dropped. | Medium |
| **SPLINE** | Free-form curves occasionally used for slab boundaries. | Low |
| **Multi-segment polylines** | A 4-point closed LWPOLYLINE representing a beam outline is stored but never decomposed into H/V segments for beam detection. | High |
| **Paper space entities** | Only modelspace is read. Layouts with viewports containing structural info are missed. | Medium |
| **ATTRIB inside INSERT** | Block attributes often contain element names (P1, V12, L3). Not extracted. | High |
| **3DFACE / MESH** | 3D structural models exported to DXF use these. Not relevant for 2D plans but worth noting. | Low |

### Structural detection gaps

- **Lajes nervuradas (ribbed slabs)**: No concept exists. The parser treats everything as either solid slab panels (derived from beam grid) or individual elements.
- **Diagonal beams**: Any beam not aligned to X or Y axes is invisible.
- **Slab openings**: Holes in slabs (elevators, stairs) are not detected or subtracted.
- **Cantilever detection**: Relies solely on convex hull of pillars, which fails for L-shaped or irregular buildings.

---

## 2. Lajes Nervuradas (Ribbed Slabs) Detection

### How ribbed slabs appear in DXF

Ribbed slabs in Brazilian structural engineering (NBR 6118) are represented differently from solid slabs:

1. **Parallel rib lines**: A series of equally-spaced parallel lines (or thin rectangles) within a slab panel, representing the ribs (nervuras). Typical spacing: 40-80cm (cubetas).
2. **Hatch patterns**: The area between ribs is often hatched with a concrete pattern. The capa (top flange) may have a different hatch or no hatch.
3. **Section callouts**: Text annotations like "LN1 (h=30, nerv. 10x25 c/50)" indicating ribbed slab with total height 30cm, rib width 10cm, rib height 25cm, spacing 50cm.
4. **Layer naming**: Layers like "LAJE_NERVURADA", "LN", "NERVURAS", or "RIBS".
5. **Block references**: Standard rib cross-section details stored as INSERT blocks.

### Detection algorithm

```python
def detect_ribbed_slab(segments: List[SegmentEntity], slab_polygon: Polygon) -> Optional[RibbedSlabInfo]:
    """
    1. Filter segments inside the slab polygon boundary
    2. Group parallel segments by direction (H or V)
    3. For each direction group, compute inter-segment spacing
    4. If spacing is uniform (stddev < 10% of mean) and count >= 3:
       -> This is a ribbed slab with ribs in that direction
    5. Rib spacing = mean distance between parallel lines
    6. Rib direction = direction of the parallel lines
    """
```

**Key parameters to extract:**
- `rib_direction`: "x" or "y" (direction ribs run)
- `rib_spacing_cm`: center-to-center distance (typically 40-80cm)
- `rib_width_cm`: width of each rib (typically 8-15cm)
- `rib_height_cm`: height of rib below the capa (typically 15-30cm)
- `capa_height_cm`: top flange thickness (typically 5-8cm)
- `total_height_cm`: rib_height + capa_height
- `cubeta_type`: "plastica" or "EPS" (affects self-weight)

### Shoring rules for ribbed slabs (NBR 15696)

- Ribbed slabs distribute load differently: ribs act as small beams
- Shore lines should run **perpendicular to rib direction** for best support
- Rib intersections (cruzamento de nervuras) need point shores
- Higher `taxa kg/m3` than solid slabs of same thickness due to formwork weight
- Standard cubeta sizes (e.g., Atex 49x49x20, 61x61x25) affect shore spacing

### Implementation approach

1. Add a `RibbedSlabCandidate` dataclass to `segment_classifier.py`
2. After `derive_slabs_from_beams()` identifies slab panels, run rib detection inside each panel
3. Use text annotations (nearby "LN", "nervurada") as confidence boost
4. Output affects the `stage_calculate` step: different self-weight formula, different shore layout

---

## 3. Block References (INSERT Entities)

### The problem

Many CAD programs (AutoCAD, BricsCAD, ZWCAD) use block references extensively:
- Standard pillar cross-sections stored as blocks and inserted at each location
- Beam details as blocks
- Title blocks, north arrows, scale bars
- Shoring equipment symbols (if reusing drawings)

Currently, `parse_dxf()` iterates over `msp` (modelspace) entities. INSERT entities appear in this iteration but are skipped because they don't match any handled `etype`.

### ezdxf API for block resolution

```python
import ezdxf

doc = ezdxf.readfile("file.dxf")
msp = doc.modelspace()

for entity in msp:
    if entity.dxftype() == "INSERT":
        insert = entity

        # Method 1: virtual_entities() — non-destructive, yields transformed copies
        # Best for reading without modifying the document
        for sub_entity in insert.virtual_entities():
            # sub_entity is already transformed to world coordinates
            # (position, rotation, scale applied)
            etype = sub_entity.dxftype()
            # Process LINE, LWPOLYLINE, CIRCLE, TEXT, etc.

        # Method 2: explode() — destructive, adds entities to layout
        # Modifies the document, useful for one-time conversion
        # exploded = insert.explode()

        # Method 3: Access block definition directly
        block = doc.blocks.get(insert.dxf.name)
        if block:
            for sub_entity in block:
                # These are in block-local coordinates
                # Need manual transform: insert.dxf.insert, .rotation, .xscale, .yscale
                pass

        # Read ATTRIB values (element names like "P1", "V12")
        for attrib in insert.attribs:
            tag = attrib.dxf.tag    # e.g., "NAME"
            value = attrib.dxf.text  # e.g., "P1"
```

### Implementation plan for `stage_parse.py`

```python
elif etype == "INSERT":
    # Resolve block reference to actual geometry
    for sub in entity.virtual_entities():
        sub_type = sub.dxftype()
        sub_layer = sub.dxf.layer if hasattr(sub.dxf, 'layer') else layer

        if sub_type == "LINE":
            # Same logic as LINE handling above
            ...
        elif sub_type in ("LWPOLYLINE", "POLYLINE"):
            ...
        elif sub_type == "SOLID":
            ...
        elif sub_type == "CIRCLE":
            ...
        elif sub_type in ("TEXT", "MTEXT"):
            ...

    # Also extract ATTRIB values as text annotations
    for attrib in entity.attribs:
        texts.append(TextEntity(
            content=attrib.dxf.text,
            x=attrib.dxf.insert.x,
            y=attrib.dxf.insert.y,
            layer=layer,
        ))
```

### Considerations

- **Nested blocks**: INSERT inside a block definition. `virtual_entities()` handles one level. For deep nesting, use recursive resolution or `ezdxf.disassemble.recursive_decompose()`.
- **XREF (external references)**: These are block references to external DXF/DWG files. `ezdxf` can read them but the external file must be available. For server-side use, XREFs should be bound first.
- **Performance**: Large files with thousands of INSERT entities can be slow with `virtual_entities()`. Cache block definitions and apply transforms manually if performance is an issue.
- **Uniform scale**: Most structural drawings use uniform scale (xscale = yscale). Non-uniform scale distorts geometry and should trigger a warning.

---

## 4. HATCH Entities for Slab Detection

### How engineers use hatching

- **Concrete fill**: ANSI31 or ANSI32 patterns mark concrete sections
- **Slab areas**: Solid or patterned hatches outline slab boundaries
- **Section cuts**: Hatched areas in cross-section views show cut elements
- **Material indication**: Different patterns for different materials (concrete, masonry, soil)

### ezdxf HATCH handling

```python
for entity in msp:
    if entity.dxftype() == "HATCH":
        hatch = entity

        # Pattern info
        pattern_name = hatch.dxf.pattern_name  # e.g., "ANSI31", "SOLID"
        is_solid = hatch.dxf.solid_fill  # True for solid fill

        # Boundary paths — the outline of the hatched area
        for path in hatch.paths:
            if path.path_type_flags & 2:  # Polyline path
                vertices = [(v.x, v.y) for v in path.vertices]
                is_closed = path.is_closed
                polygon = Polygon(vertices)

            else:  # Edge path (composed of line/arc/ellipse/spline edges)
                points = []
                for edge in path.edges:
                    if edge.EDGE_TYPE == 'LineEdge':
                        points.append((edge.start.x, edge.start.y))
                        points.append((edge.end.x, edge.end.y))
                    elif edge.EDGE_TYPE == 'ArcEdge':
                        # Discretize arc into points
                        ...
                    elif edge.EDGE_TYPE == 'EllipseEdge':
                        ...
                    elif edge.EDGE_TYPE == 'SplineEdge':
                        ...
                # Build polygon from collected points

        # Associated source boundary entities (if linked)
        # hatch.source_boundary_objects  # handles to boundary entities
```

### Implementation plan

1. Add `HatchEntity` dataclass to `stage_parse.py`:
   ```python
   @dataclass
   class HatchEntity:
       polygon: List[Tuple[float, float]]  # boundary vertices
       pattern_name: str
       is_solid: bool
       layer: str
       area: float
   ```

2. In `parse_dxf()`, extract HATCH boundaries as polygons.

3. In `stage_classify.py`, use HATCH polygons to:
   - Confirm slab areas (if hatch covers a beam-grid polygon, boost slab confidence)
   - Detect slab areas that the beam-grid method missed (standalone hatched regions on slab layers)
   - Identify slab openings (hatched areas with specific patterns inside a slab polygon)

4. Filter by layer name: hatches on layers containing "LAJE", "SLAB", "CONCRETO" are strong slab indicators.

### Caveats

- Many DXF files have decorative hatching (title block fills, ground patterns). Filter by layer.
- HATCH boundary paths can be complex (arc edges, spline edges). Start with polyline paths only, handle edge paths as a follow-up.
- Some hatches reference external boundary entities. If the boundary entities are missing, fall back to the path vertices.

---

## 5. DIMENSION Entities for Extracting Measurements

### Why dimensions matter

Structural drawings contain DIMENSION entities that encode:
- Beam section dimensions (e.g., "14x50" as a dimension on a detail view)
- Span lengths between pillars
- Slab panel dimensions
- Floor-to-floor heights
- Cantilever lengths

Currently, only TEXT/MTEXT annotations are parsed. DIMENSION entities have a separate structure.

### ezdxf DIMENSION handling

```python
for entity in msp:
    if entity.dxftype() == "DIMENSION":
        dim = entity

        # The actual measured value
        measurement = dim.dxf.actual_measurement  # float, in drawing units

        # Override text (if engineer typed custom text)
        text_override = dim.dxf.text  # "" means use actual_measurement
        # "<>" means use actual_measurement with formatting
        # Any other string is the override text

        # Dimension type
        dim_type = dim.dimtype  # 0=linear, 1=aligned, 2=angular, 3=diameter, 4=radius, 5=angular3p, 6=ordinate

        # Key points
        defpoint = dim.dxf.defpoint     # definition point (end of first extension line)
        defpoint2 = dim.dxf.defpoint2   # second definition point (for linear dims)
        defpoint3 = dim.dxf.defpoint3   # dimension line location
        text_midpoint = dim.dxf.text_midpoint  # where the text is placed

        # The virtual geometry (lines, arrows, text)
        # Use virtual_entities() to get the visual representation
        for sub in dim.virtual_entities():
            # LINE entities for dimension/extension lines
            # TEXT/MTEXT for the dimension value
            pass
```

### Implementation plan

1. Extract DIMENSION entities in `parse_dxf()`:
   ```python
   @dataclass
   class DimensionEntity:
       measurement: float  # actual value in drawing units
       text: str           # override text or formatted measurement
       x: float            # text midpoint x
       y: float            # text midpoint y
       dim_type: int       # 0=linear, 1=aligned, etc.
       layer: str
   ```

2. In classification, use dimensions near beam/slab elements to:
   - Confirm span lengths
   - Extract section dimensions when text classifier misses them
   - Validate scale detection (if dimension says "5.00" and geometric distance is 500 units, scale is 1:100)

3. Use dimension values for scale validation: compare `actual_measurement` to geometric distance between definition points.

---

## 6. DWG Support

### Current state

The project already has `src/parser/dwg_converter.py` with ODA File Converter support. This is the right approach.

### Options comparison

| Tool | Platform | License | Quality | Speed | Notes |
|---|---|---|---|---|---|
| **ODA File Converter** | Win/Mac/Linux | Free (registration) | Excellent | Fast | Already implemented. Best option. |
| **LibreCAD** | Win/Mac/Linux | GPL | Good | Slow | CLI: `libreoffice --headless --convert-to dxf`. Loses some entities. |
| **TeighaFileConverter** | Win/Mac/Linux | Commercial | Excellent | Fast | Same as ODA (rebranded). |
| **FreeCAD** | Win/Mac/Linux | LGPL | Fair | Slow | Python: `import FreeCAD; FreeCAD.openDocument("file.dwg")`. Incomplete DWG support. |
| **QCAD** | Win/Mac/Linux | GPL | Good | Medium | CLI conversion available. |

### Python-only approaches (no external converter)

- **`dwg-python`** (pypi: `dwg`): Experimental, very limited entity support. Not production-ready.
- **`ezdxf` with `odafc` addon**: ezdxf 0.18+ includes `ezdxf.addons.odafc` which wraps ODA File Converter programmatically:
  ```python
  from ezdxf.addons import odafc

  # Convert DWG to DXF (requires ODA installed)
  doc = odafc.readfile("input.dwg")
  doc.saveas("output.dxf")
  ```
  This is cleaner than subprocess calls and handles temp files automatically.

### Server-side deployment recommendation

1. **Docker**: Include ODA File Converter in the Docker image:
   ```dockerfile
   # Download ODA from https://www.opendesign.com/guestfiles/oda_file_converter
   COPY ODAFileConverter_QT6_lnxX64_8.3dll_25.4.deb /tmp/
   RUN dpkg -i /tmp/ODAFileConverter_QT6_lnxX64_8.3dll_25.4.deb
   ```

2. **Fallback chain**: Try `ezdxf.addons.odafc` first, then subprocess to ODA, then reject with clear error message.

3. **Async conversion**: DWG conversion can take 2-10 seconds for large files. Run in a background task with progress callback.

### Improvements to existing `dwg_converter.py`

- Add the `ezdxf.addons.odafc` method as primary approach
- Add timeout handling (large DWG files can take long)
- Add version detection for the output DXF format
- Support batch conversion (multiple files)
- Add validation: verify the output DXF is readable by ezdxf before returning

---

## 7. IFC Format Support

### What is IFC

IFC (Industry Foundation Classes, ISO 16739) is the open BIM standard. Unlike DXF (which stores geometry), IFC stores **semantic building models**: each element knows what it is (beam, slab, column) and carries properties (material, section, loads).

### ifcopenshell library

```python
import ifcopenshell

model = ifcopenshell.open("structure.ifc")

# Get all structural elements by type
slabs = model.by_type("IfcSlab")
beams = model.by_type("IfcBeam")
columns = model.by_type("IfcColumn")
walls = model.by_type("IfcWall")

for slab in slabs:
    # Name and description
    name = slab.Name        # e.g., "L1"

    # Geometry (requires ifcopenshell.geom)
    import ifcopenshell.geom
    settings = ifcopenshell.geom.settings()
    shape = ifcopenshell.geom.create_shape(settings, slab)
    # shape.geometry contains vertices and faces

    # Properties (material, thickness, etc.)
    for rel in slab.IsDefinedBy:
        if rel.is_a("IfcRelDefinesByProperties"):
            pset = rel.RelatingPropertyDefinition
            if pset.is_a("IfcPropertySet"):
                for prop in pset.HasProperties:
                    print(f"{prop.Name}: {prop.NominalValue.wrappedValue}")

    # Placement (position in building)
    placement = slab.ObjectPlacement

    # Material
    for rel in slab.HasAssociations:
        if rel.is_a("IfcRelAssociatesMaterial"):
            material = rel.RelatingMaterial
```

### Advantages over DXF for shoring calculation

| Aspect | DXF | IFC |
|---|---|---|
| Element identification | Must infer from geometry + text | Explicit: IfcSlab, IfcBeam, IfcColumn |
| Section dimensions | Must parse from text annotations | Stored as IfcProfileDef properties |
| Material | Not available | IfcMaterial with density, strength |
| Floor levels | Must detect from text/filename | IfcBuildingStorey hierarchy |
| Slab thickness | Must parse from text | IfcSlab with thickness property |
| Openings | Must detect geometrically | IfcOpeningElement with exact geometry |
| Load information | Not available | Can include IfcStructuralLoadCase |
| Rebar | Not relevant (2D) | IfcReinforcingBar with positioning |

### Implementation plan

1. Add `ifcopenshell` to dependencies (pip install ifcopenshell)
2. Create `src/parser/ifc_reader.py`:
   - Extract slabs with boundaries, thickness, material
   - Extract beams with section profiles, spans
   - Extract columns with positions, sections
   - Map to existing `ClassifiedElement` model
3. Create `src/pipeline/stage_parse_ifc.py` that produces the same `ParseResult`-like output
4. In `runner.py`, detect file extension and route to DXF or IFC parser

### Caveats

- IFC files from structural engineers (TQS, Cypecad, ETABS) may not include architectural elements, which is actually ideal for shoring
- IFC export quality varies enormously between software. TQS exports excellent structural IFC; some programs export geometry-only without properties
- ifcopenshell requires compilation (C++ backend). Pre-built wheels available for most platforms via `pip install ifcopenshell`
- IFC4 vs IFC2x3: older files use IFC2x3, newer use IFC4. ifcopenshell handles both

---

## 8. Multi-Scale / Multi-Viewport DXF Files

### The problem

Real structural drawings contain multiple scales in one file:
- **Main floor plan** at 1:50 (shows all beams, pillars, slabs)
- **Detail views** at 1:25 or 1:20 (beam-pillar connections, reinforcement details)
- **Cross-sections** at 1:25 (shows slab thickness, beam heights)
- **General layout** at 1:100 or 1:200 (overview)
- **Title block** at 1:1 (paper space)

### Model space vs paper space

```python
doc = ezdxf.readfile("file.dxf")

# Model space — all geometry at real-world scale (or dominant scale)
msp = doc.modelspace()

# Paper space layouts — arranged for printing
for layout in doc.layouts:
    if layout.name == "Model":
        continue  # skip modelspace

    for entity in layout:
        if entity.dxftype() == "VIEWPORT":
            vp = entity
            # Viewport properties
            center = vp.dxf.center        # center in paper space
            width = vp.dxf.width          # viewport width in paper units
            height = vp.dxf.height        # viewport height in paper units
            view_center = vp.dxf.view_center_point  # center of view in model space
            view_height = vp.dxf.view_height         # height of view in model space

            # Scale = paper_height / model_height
            scale = height / view_height if view_height else 1.0
```

### Handling multiple scales in model space

When multiple detail views exist in model space (common in Brazilian structural engineering), they appear as groups of entities at different locations, often surrounded by a border rectangle.

**Detection strategy:**

1. **Cluster entities spatially**: Use DBSCAN or grid-based clustering to identify distinct drawing regions.
2. **Identify the main plan**: The largest cluster (by bounding box area) is typically the main structural plan.
3. **Detect detail borders**: Look for closed rectangles with text annotations like "DETALHE", "CORTE", "SEÇÃO" nearby.
4. **Scale per region**: Each region may have a scale annotation ("ESC 1:25"). Use the existing `scale_detector.py` within each region.
5. **Process only the main plan**: For shoring calculation, focus on the largest plan view. Detail views provide supplementary info (section dimensions) but should not be mixed into the main structural detection.

### Implementation approach

```python
def identify_drawing_regions(parse_result: ParseResult) -> List[DrawingRegion]:
    """
    1. Compute bounding box of ALL entities
    2. Look for rectangular borders (closed polylines/rectangles near the full extents)
    3. If no clear borders, use spatial clustering
    4. Classify each region:
       - "PLAN" (main floor plan) — largest region
       - "SECTION" (cross-section) — contains "CORTE" or "SEÇÃO" text
       - "DETAIL" (detail view) — contains "DETALHE" text
       - "TITLE" (title block) — bottom-right, contains project info
    5. Return regions with their local scale and purpose
    """
```

### Current `scale_detector.py` integration

The existing scale detector looks for text patterns like "1:50", "ESC:", "ESCALA". Enhancement needed:
- Detect multiple scales in the same file
- Associate each scale with a spatial region
- Use the main plan's scale as the primary scale
- Warn if no scale is detected (common in cm-unit drawings)

---

## Priority Roadmap

| Priority | Item | Effort | Impact |
|---|---|---|---|
| 1 | INSERT block resolution | Medium (2-3 days) | Critical — many files use blocks for pillars |
| 2 | Multi-segment polyline decomposition | Small (1 day) | High — beams often drawn as polylines |
| 3 | HATCH boundary extraction | Medium (2-3 days) | High — slab area confirmation |
| 4 | DIMENSION entity reading | Small (1 day) | Medium — section dimensions, scale validation |
| 5 | Ribbed slab detection | Large (3-5 days) | High — common slab type in Brazil |
| 6 | Multi-scale region detection | Medium (2-3 days) | Medium — prevents detail views corrupting detection |
| 7 | IFC support | Large (5-7 days) | High but deferred — semantic model eliminates guessing |
| 8 | DWG converter improvements | Small (1 day) | Low — already functional |
