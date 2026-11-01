# BeSeated Map Format

> Provided by the BeSeated backend (26 Oct 2026). The single reference for the output format of
> stages 6 and 7; project decisions are in `technical-setup.md`, section 5.5.

How to create a floor map (floors, rooms, desks) that matches the maps in BeSeated.
Importing a map into BeSeated is a separate step and is not covered here.

## 1. How BeSeated represents a map

A map is **not** an image or an SVG. A floor is an empty canvas, and every room and desk on it is a
positioned rectangle stored as a database row. The frontend draws the map from these rectangles.

```
Location          one office site (e.g. Hamburg)
 └── Floor        one map / canvas (e.g. "10. OG")
      └── FloorDistribution    one element on the map: room, desk, parking lot, label, icon
           └── Reservation      a booking of one element
```

Backend classes:

| Concept           | Entity                                     | REST model                        |
|-------------------|--------------------------------------------|-----------------------------------|
| Location          | `backend/entity/LocationEntity.java`        | `rest/model/Location.java`        |
| Floor             | `backend/entity/FloorEntity.java`           | `rest/model/Floor.java`           |
| FloorDistribution | `backend/entity/FloorDistributionEntity.java` | `rest/model/FloorDistribution.java` |
| Element types     | –                                          | `rest/model/FloorDistributionType.java` |
| Icons             | `backend/entity/Icon.java`                  | `rest/model/Icon.java`            |

Desks are not linked to rooms in the data. A desk looks like it belongs to a room only because its
rectangle lies inside the room's rectangle and is drawn on a higher layer.

## 2. Coordinate system

- Origin `(0,0)` is the **top-left** corner of the floor. `x` grows to the right and `y` grows downwards.
- `x`/`y` is the **top-left corner** of an element.
- Coordinates are **absolute on the floor**, not relative to the containing room.
  Example from the existing data: room "Teamleitung HR" is at `x=0, y=265, width=121, height=84`,
  and its desk "HR" is at `x=35, y=321`, which is inside the room.
- `width` is the horizontal size and `height` the vertical size, both integers.
- `z` is the drawing layer: higher values are drawn on top.

Typical sizes in the existing maps:

| Element          | width × height              |
|------------------|-----------------------------|
| Room             | about 115–121 wide, height varies (60–150) |
| Desk, horizontal | 40 × 20                     |
| Desk, vertical   | 20 × 40                     |
| Desk, square     | 20 × 20                     |

> The unit (presumably pixels at a fixed scale) and any maximum canvas size are defined in the
> frontend, not in this backend. Check the frontend's map component before fixing your scale.
> Until then, stay in the same size range as the existing maps.

## 3. The map file format

One JSON file per floor. Field names and values are exactly those of the BeSeated REST API, so a map
can later be imported without conversion. Leave out `id` and `floorId`, because BeSeated assigns them
during import.

```json
{
  "floor": {
    "locationId": 11,
    "name": "11. OG",
    "number": 11,
    "main": false,
    "type": "workspace"
  },
  "distributions": [
    {
      "name": "Team-Raum",
      "type": "ROOM",
      "shape": "Viereck",
      "x": 0, "y": 0, "z": 0,
      "width": 121, "height": 84,
      "reservable": false, "requestable": false, "locked": false,
      "owner": null, "notification": null,
      "icons": []
    },
    {
      "name": "HH-11OG-T1",
      "type": "TABLE",
      "shape": "Viereck",
      "x": 20, "y": 20, "z": 2,
      "width": 40, "height": 20,
      "reservable": true, "requestable": true, "locked": false,
      "owner": null, "notification": null,
      "icons": []
    },
    {
      "name": "HH-11OG-T2",
      "type": "TABLE",
      "shape": "Viereck",
      "x": 20, "y": 50, "z": 2,
      "width": 40, "height": 20,
      "reservable": true, "requestable": true, "locked": false,
      "owner": null, "notification": null,
      "icons": []
    },
    {
      "name": "Küche",
      "type": "ROOM",
      "shape": "Viereck",
      "x": 0, "y": 90, "z": 0,
      "width": 121, "height": 60,
      "reservable": false, "requestable": false, "locked": false,
      "owner": null, "notification": null,
      "icons": ["KITCHEN"]
    }
  ]
}
```

To compare with a real map, an existing floor can be fetched from the API. It returns the same
structure as `distributions`, plus `id` and `floorId`:

```
GET /BeSeated/api/locations/{locationId}/floors/{floorId}/floor-distributions
```

## 4. Field reference

### 4.1 Floor

| Field        | Type    | Required | Rules |
|--------------|---------|----------|-------|
| `locationId` | integer | yes | Id of an existing location (`GET /BeSeated/api/locations`) |
| `name`       | string  | yes | Display name, e.g. `"2. OG"`. **Max 25 characters** (DB column `char(25)`) |
| `number`     | integer | yes | Floor number, used for ordering. May be negative (`-2` = underground car park) |
| `main`       | boolean | yes | `true` = floor shown by default for the location. **Exactly one floor per location** |
| `active`     | boolean | no  | Inactive floors are hidden by the API. Default `true` |
| `type`       | string  | yes | `"workspace"` (offices) or `"parkingLot"` (parking) |

### 4.2 Distribution (room, desk, …)

| Field          | Type           | Required | Rules |
|----------------|----------------|----------|-------|
| `name`         | string         | yes | **Max 30 characters**. May be `""` for unnamed rooms |
| `type`         | string         | yes | `ROOM`, `TABLE`, `PARKING_LOT`, `ORIENTATION`, `ICON` |
| `shape`        | string         | yes | `"Viereck"` (rectangle) or `"Kreis"` (circle inside the width×height box). Almost everything is `Viereck` |
| `x`, `y`       | integer ≥ 0    | yes | Top-left corner, absolute on the floor |
| `width`, `height` | integer ≥ 1 | yes | Size |
| `z`            | integer ≥ 0    | yes | Layer. Convention: `0` room, `1` orientation/parking, `2` desk |
| `reservable`   | boolean        | yes | Can be booked directly |
| `requestable`  | boolean        | yes | Can be requested through the approval workflow (Camunda) |
| `locked`       | boolean        | yes | Temporarily blocked |
| `owner`        | email or null  | no  | If set, only this person can book it. **Max 50 characters** |
| `notification` | string or null | no  | Hint shown to users, e.g. `"Nur buchbar von Max Mustermann"`. **Max 50 characters** |
| `icons`        | array          | yes | Unique values from the icon list below; `[]` for none |

### 4.3 Element types

| Type          | Meaning | Typical settings |
|---------------|---------|------------------|
| `ROOM`        | Room outline (background) | `z: 0`, `reservable: false` |
| `TABLE`       | Bookable desk | `z: 2`, `reservable: true`, `requestable: true` |
| `PARKING_LOT` | Parking space | on floors with `type: "parkingLot"` |
| `ORIENTATION` | Labels/markers for orientation (e.g. "Chill Area") | `z: 1`, not reservable |
| `ICON`        | Pure symbol element | not reservable, with `icons` set |

### 4.4 Icons

`WC_MEN`, `WC_WOMEN`, `DOG`, `KITCHEN`, `TELEPHONE_BOOTH`, `LOUD`, `SILENT`, `ELEVATOR`, `LUNCH`,
`SERVER_ROOM`, `TEA`, `STAIRCASE`, `ENTRANCE`, `ESCAPE_ROUTE`, `FIRE_EXTINGUISHER`, `FIRST_AID_KIT`

Icons can be attached to any element, e.g. a `ROOM` named "Küche" with `["KITCHEN"]`.

## 5. Rules a valid map must follow

### Hard rules (BeSeated or the database would reject or break otherwise)

1. All required fields are present with the right types (see section 4).
2. Length limits: floor name ≤ 25, element name ≤ 30, owner ≤ 50, notification ≤ 50 characters.
3. `type`, `shape`, floor `type` and `icons` only use the listed values, spelled exactly as listed.
   A wrong `type` value breaks loading the **entire** floor, not just that element.
4. `width`/`height` are positive and `x`/`y` are not negative.
5. `owner`, if set, is a valid e-mail address.

### Conventions (not enforced, but all existing maps follow them)

1. Every desk (`TABLE`) lies **completely inside** a room (`ROOM`).
2. Desks don't overlap each other, and rooms don't overlap each other.
3. Rooms use `z: 0` and desks use `z: 2`.
4. Rooms are not reservable.
5. Every desk is `reservable` or `requestable`, otherwise nobody can book it.
6. Desk names are unique per floor and follow `<site>-<floor>-T<n>`, e.g. `HH-1OG-T5`.
7. Sizes are in the range of the existing maps (section 2).

## 6. JSON Schema

This schema checks the hard rules. The geometric conventions (containment, overlap) cannot be
expressed in JSON Schema and must be checked separately.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "BeSeated floor map",
  "type": "object",
  "required": ["floor", "distributions"],
  "additionalProperties": false,
  "properties": {
    "floor": { "$ref": "#/$defs/floor" },
    "distributions": {
      "type": "array",
      "items": { "$ref": "#/$defs/distribution" }
    }
  },
  "$defs": {
    "floor": {
      "type": "object",
      "required": ["locationId", "name", "number", "main", "type"],
      "additionalProperties": false,
      "properties": {
        "locationId": { "type": "integer", "minimum": 0 },
        "name":       { "type": "string", "minLength": 1, "maxLength": 25 },
        "number":     { "type": "integer" },
        "main":       { "type": "boolean" },
        "active":     { "type": "boolean", "default": true },
        "type":       { "type": "string", "enum": ["workspace", "parkingLot"] }
      }
    },
    "distribution": {
      "type": "object",
      "required": [
        "name", "type", "shape",
        "x", "y", "z", "width", "height",
        "reservable", "requestable", "locked",
        "icons"
      ],
      "additionalProperties": false,
      "properties": {
        "name":   { "type": "string", "maxLength": 30 },
        "type":   { "type": "string", "enum": ["ROOM", "TABLE", "PARKING_LOT", "ORIENTATION", "ICON"] },
        "shape":  { "type": "string", "enum": ["Viereck", "Kreis"] },
        "x":      { "type": "integer", "minimum": 0 },
        "y":      { "type": "integer", "minimum": 0 },
        "z":      { "type": "integer", "minimum": 0 },
        "width":  { "type": "integer", "minimum": 1 },
        "height": { "type": "integer", "minimum": 1 },
        "reservable":  { "type": "boolean" },
        "requestable": { "type": "boolean" },
        "locked":      { "type": "boolean" },
        "owner":        { "type": ["string", "null"], "format": "email", "maxLength": 50 },
        "notification": { "type": ["string", "null"], "maxLength": 50 },
        "icons": {
          "type": "array",
          "uniqueItems": true,
          "items": {
            "type": "string",
            "enum": [
              "WC_MEN", "WC_WOMEN", "DOG", "KITCHEN", "TELEPHONE_BOOTH",
              "LOUD", "SILENT", "ELEVATOR", "LUNCH", "SERVER_ROOM", "TEA",
              "STAIRCASE", "ENTRANCE", "ESCAPE_ROUTE", "FIRE_EXTINGUISHER",
              "FIRST_AID_KIT"
            ]
          }
        }
      }
    }
  }
}
```

## 7. Checking the geometric conventions

With `x1 = x`, `y1 = y`, `x2 = x + width`, `y2 = y + height` for each element:

- **Desk D is inside room R** if
  `R.x1 <= D.x1 && R.y1 <= D.y1 && D.x2 <= R.x2 && D.y2 <= R.y2`
- **A and B overlap** if
  `A.x1 < B.x2 && B.x1 < A.x2 && A.y1 < B.y2 && B.y1 < A.y2`
  (touching edges do not count as overlap)

For circles (`"Kreis"`), use the width × height bounding box.

## 8. Checklist before handing over a map

- [ ] File validates against the JSON Schema (section 6)
- [ ] Exactly one floor per location has `main: true`
- [ ] Every `TABLE` is completely inside a `ROOM`
- [ ] No overlapping desks, no overlapping rooms
- [ ] Rooms `z: 0`, desks `z: 2`
- [ ] Every desk is `reservable` and/or `requestable`
- [ ] Desk names are unique per floor (`<site>-<floor>-T<n>`)
- [ ] Sizes are comparable to an existing floor (compare via the GET endpoint in section 3)

## 9. Open questions (answer from the frontend before finalizing)

- What unit the coordinates are in, and the scale at which the frontend draws them.
- Whether there is a maximum canvas size per floor.
- How `"Kreis"` and the `ORIENTATION`/`ICON` types are rendered exactly.

> Answered by the frontend (summary in `technical-setup.md`, section 5.5): units have no fixed
> meaning, but text and icon sizes are fixed in map units, so maps must match the existing scale;
> there is no maximum canvas size (the `viewBox` fits all elements).
