async def test_previsit_briefing_returns_matching_available_inventory(
    client, sales_headers
):
    customer_response = await client.post(
        "/api/customers",
        headers=sales_headers,
        json={"full_name": "Appointment Customer"},
    )
    assert customer_response.status_code == 201
    customer_id = customer_response.json()["id"]

    car_response = await client.post(
        f"/api/customers/{customer_id}/cars",
        headers=sales_headers,
        json={"make": "Volkswagen", "model": "Tiguan", "year": 2022},
    )
    assert car_response.status_code == 201

    matching_response = await client.post(
        "/api/inventory",
        headers=sales_headers,
        json={
            "make": "Volkswagen",
            "model": "Tiguan",
            "year": 2026,
            "status": "available",
        },
    )
    assert matching_response.status_code == 201
    matching_id = matching_response.json()["id"]

    other_response = await client.post(
        "/api/inventory",
        headers=sales_headers,
        json={
            "make": "Toyota",
            "model": "RAV4",
            "year": 2026,
            "status": "available",
        },
    )
    assert other_response.status_code == 201

    sold_response = await client.post(
        "/api/inventory",
        headers=sales_headers,
        json={
            "make": "Volkswagen",
            "model": "Atlas",
            "year": 2025,
            "status": "sold",
        },
    )
    assert sold_response.status_code == 201

    response = await client.post(
        f"/api/customers/{customer_id}/briefing", headers=sales_headers
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["triggered_count"] == 0
    assert [item["id"] for item in body["inventory"]] == [matching_id]

