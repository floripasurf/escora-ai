DESIGN_PAYLOAD = {
    "floors": 1,
    "target_area_m2": 60,
    "bedrooms": 2,
    "bathrooms": 1,
    "layout_type": "open_kitchen",
    "has_garage": False,
    "lot_width_m": 8,
    "lot_depth_m": 20,
    "block_size": "14",
    "region": "sudeste",
    "soil_capacity_kpa": 100,
    "ceiling_height_m": 2.8,
    "roof_type": "wooden_truss",
}


DRAWING_PAYLOAD = {
    "format": "A4",
    "scale": "1:50",
    "walls": [
        {"x1": 0, "y1": 0, "x2": 4, "y2": 0},
        {"x1": 4, "y1": 0, "x2": 4, "y2": 3},
        {"x1": 4, "y1": 3, "x2": 0, "y2": 3},
        {"x1": 0, "y1": 3, "x2": 0, "y2": 0},
    ],
    "sections": [
        {"label": "A", "start": [0, 1.5], "end": [4, 1.5], "direction": "north"}
    ],
}


def test_design_generation_requires_authenticated_branch(client_unauth):
    for endpoint in ("/api/v1/design/alternatives", "/api/v1/design/preview"):
        response = client_unauth.post(endpoint, json=DESIGN_PAYLOAD)

        assert response.status_code == 401


def test_drawing_generation_requires_authenticated_branch(client_unauth):
    for endpoint in (
        "/api/v1/drawing/floor-plan",
        "/api/v1/drawing/section",
        "/api/v1/drawing/perspective",
    ):
        response = client_unauth.post(endpoint, json=DRAWING_PAYLOAD)

        assert response.status_code == 401
