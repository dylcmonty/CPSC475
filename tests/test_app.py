"""End-to-end tests of every page against a real PostgreSQL database."""


def add_crop(client, taxon_id, farm_id=1):
    return client.post(f"/farms/{farm_id}/catalog/add", data={"taxon_id": taxon_id})


def add_plot(client, name, area="", farm_id=1):
    return client.post(f"/farms/{farm_id}/plots/new", data={"name": name, "area_sq_m": area})


def add_event(client, farm_id=1, **fields):
    data = {"event_kind_code": "harvest", "taxon_id": "4", "event_date": "2025-07-20",
            "quantity": "", "unit": "", "plot_id": "", "product_id": "", "notes": ""}
    data.update(fields)
    return client.post(f"/farms/{farm_id}/events/new", data=data, follow_redirects=True)


# --- Real data and search -------------------------------------------------

def test_home_shows_table_counts_and_coverage(client):
    page = client.get("/").get_data(as_text=True)
    assert "market_lot" in page
    assert "Test Auction B" in page
    assert "50.0" in page  # one of the two lots from source B is matched


def test_search_matches_names_and_ranks_by_evidence(client):
    page = client.get("/search?q=garlic").get_data(as_text=True)
    assert "Allium sativum" in page and "Allium vineale" in page
    assert page.index("Allium sativum") < page.index("Allium vineale")


def test_search_treats_wildcards_literally(client):
    page = client.get("/search?q=%25").get_data(as_text=True)
    assert "Nothing matches" in page


def test_price_curve_groups_by_month_across_seasons(client):
    page = client.get("/taxa/4").get_data(as_text=True)
    assert "Seasonal price curve" in page
    assert "<td>Jul</td><td class=\"num\">2</td><td class=\"num\">2</td>" in page
    assert "$8.00" in page and "$10.50" in page and "$13.00" in page


def test_price_curve_is_drawn_per_unit(client):
    page = client.get("/taxa/4").get_data(as_text=True)
    assert "per <strong>bag</strong>" in page          # the most common unit
    assert "unit=peck" in page                           # the other unit is offered
    page = client.get("/taxa/4", query_string={"unit": "peck"}).get_data(as_text=True)
    assert "per <strong>peck</strong>" in page
    assert "$4.00" in page and "$10.50" not in page    # bag prices are not mixed in


def test_unknown_taxon_is_404(client):
    assert client.get("/taxa/999").status_code == 404


# --- Farms -----------------------------------------------------------------

def test_farm_list_and_search(client):
    page = client.get("/farms/?q=holmes").get_data(as_text=True)
    assert "Test Farm" in page and "Other Farm" not in page


def test_add_farm(client, sql):
    response = client.post("/farms/new", data={"name": "New Farm", "region_id": "3",
                                               "domain": "", "owner_email": ""})
    assert response.status_code == 302
    assert sql("SELECT name FROM farm WHERE farm_id = 3") == [("New Farm",)]


# --- Plots -------------------------------------------------------------------

def test_plot_insert_update_delete(client, sql):
    add_plot(client, "North field", "120.5")
    plot_id = sql("SELECT plot_id FROM plot WHERE name = 'North field'")[0][0]

    client.post(f"/farms/1/plots/{plot_id}/edit", data={"name": "North", "area_sq_m": "130"})
    assert sql("SELECT name, area_sq_m FROM plot")[0][0] == "North"

    client.post(f"/farms/1/plots/{plot_id}/delete")
    assert sql("SELECT COUNT(*) FROM plot") == [(0,)]


def test_duplicate_plot_name_is_explained(client):
    add_plot(client, "North field")
    page = add_plot(client, "North field").get_data(as_text=True)
    assert "already has a plot with that name" in page


def test_negative_area_is_rejected_by_check_constraint(client):
    page = add_plot(client, "Bad", "-5").get_data(as_text=True)
    assert "area must be greater than zero" in page


def test_deleting_a_plot_keeps_its_events(client, sql):
    add_crop(client, 4)
    add_plot(client, "North field")
    plot_id = sql("SELECT plot_id FROM plot")[0][0]
    add_event(client, plot_id=str(plot_id), quantity="40", unit="lb")

    client.post(f"/farms/1/plots/{plot_id}/delete")
    assert sql("SELECT plot_id, quantity FROM farm_event") == [(None, 40)]


def test_cannot_change_another_farms_plot(client, sql):
    add_plot(client, "Theirs", farm_id=2)
    plot_id = sql("SELECT plot_id FROM plot")[0][0]
    client.post(f"/farms/1/plots/{plot_id}/delete")
    assert client.get(f"/farms/1/plots/{plot_id}/edit").status_code == 404
    assert sql("SELECT COUNT(*) FROM plot") == [(1,)]


# --- Crop catalog ------------------------------------------------------------

def test_catalog_insert_update_delete(client, sql):
    page = add_crop(client, 4).get_data(as_text=True)
    page = client.get("/farms/1/catalog/").get_data(as_text=True)
    assert "onion" in page

    page = client.get("/farms/1/catalog/", query_string={"q": "garlic"}).get_data(as_text=True)
    assert "Allium sativum" in page

    add_crop(client, 4)
    assert sql("SELECT COUNT(*) FROM crop_catalog") == [(1,)]

    client.post("/farms/1/catalog/4/edit", data={"notes": "Copra, 2 beds"})
    assert sql("SELECT notes FROM crop_catalog") == [("Copra, 2 beds",)]

    client.post("/farms/1/catalog/4/delete")
    assert sql("SELECT COUNT(*) FROM crop_catalog") == [(0,)]


# --- Events --------------------------------------------------------------------

def test_event_insert_update_delete(client, sql):
    add_crop(client, 4)
    page = add_event(client, quantity="40", unit="lb", notes="first pull").get_data(as_text=True)
    assert "Event recorded." in page and "first pull" in page

    event_id = sql("SELECT event_id FROM farm_event")[0][0]
    assert "first pull" in client.get(f"/farms/1/events/{event_id}/edit").get_data(as_text=True)

    client.post(f"/farms/1/events/{event_id}/edit", data={
        "event_kind_code": "harvest", "taxon_id": "4", "event_date": "2025-07-21",
        "quantity": "55", "unit": "lb", "plot_id": "", "product_id": "1", "notes": ""})
    assert sql("SELECT quantity, product_id FROM farm_event") == [(55, 1)]

    client.post(f"/farms/1/events/{event_id}/delete")
    assert sql("SELECT COUNT(*) FROM farm_event") == [(0,)]


def test_quantity_without_unit_is_rejected(client, sql):
    add_crop(client, 4)
    page = add_event(client, quantity="10").get_data(as_text=True)
    assert "must also have a unit" in page
    assert sql("SELECT COUNT(*) FROM farm_event") == [(0,)]


def test_bad_date_is_rejected_before_the_database(client):
    add_crop(client, 4)
    page = add_event(client, event_date="July 4th").get_data(as_text=True)
    assert "must be a date" in page


def test_event_cannot_use_another_farms_plot(client, sql):
    add_crop(client, 4)
    add_plot(client, "Theirs", farm_id=2)
    plot_id = sql("SELECT plot_id FROM plot")[0][0]
    page = add_event(client, plot_id=str(plot_id)).get_data(as_text=True)
    assert "does not belong to this farm" in page


def test_event_form_asks_for_a_crop_first(client):
    page = client.get("/farms/1/events/new").get_data(as_text=True)
    assert "no crops in its catalog" in page


def test_activity_history_filters(client):
    add_crop(client, 4)
    add_crop(client, 5)
    add_event(client, event_kind_code="plant", event_date="2025-04-01")
    add_event(client, taxon_id="5", event_date="2025-07-01", notes="garlic harvest")

    page = client.get("/farms/1/events/", query_string={"kind": "plant"}).get_data(as_text=True)
    assert "Planting" in page and "garlic harvest" not in page

    page = client.get("/farms/1/events/", query_string={"taxon_id": "5"}).get_data(as_text=True)
    assert "garlic harvest" in page

    page = client.get("/farms/1/events/", query_string={"from": "2025-06-01"}).get_data(as_text=True)
    assert "garlic harvest" in page and "2025-04-01" not in page


# --- Multi-table join -----------------------------------------------------------

def test_harvest_vs_market_uses_30_day_window(client):
    add_crop(client, 4)
    add_event(client, event_date="2025-07-20", quantity="40", unit="lb")
    page = client.get("/farms/1/harvest-prices").get_data(as_text=True)
    # 2025-07-15 and 2025-08-15 are within 30 days; 2024-07-10 is not.
    assert "Yellow onion" in page
    assert '<td class="num">2</td>' in page
    assert "$7.00" in page and "$13.00" in page and "$10.00" in page


def test_harvest_vs_market_keeps_units_apart(client):
    add_crop(client, 4)
    add_event(client, event_date="2025-07-20", quantity="40", unit="lb")
    page = client.get("/farms/1/harvest-prices").get_data(as_text=True)
    assert "<td>bag</td>" in page and "<td>peck</td>" in page
    assert "$4.00" in page                               # the peck lot, on its own row


def test_plantings_are_not_in_harvest_report(client):
    add_crop(client, 4)
    add_event(client, event_kind_code="plant", event_date="2025-07-20")
    assert "No harvests" in client.get("/farms/1/harvest-prices").get_data(as_text=True)
