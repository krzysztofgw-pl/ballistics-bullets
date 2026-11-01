# Contributing

Thank you for helping. Every addition and correction goes through a pull request that a
maintainer reviews; nothing is published without that review.

## Two ways to contribute

1. **From the app.** In the ammo editor, use *Suggest to the bullet database*. Suggestions are
   collected once a day into a pull request here.
2. **On GitHub.** Edit the maker's file in [`bullets/`](bullets) (or add a new one) and open a
   pull request. GitHub's web editor is enough.

## Rules

- **Published figures only.** Use the manufacturer's catalogue, website or box, or your own
  Doppler radar measurement. BCs trued to your own rifle belong in your profile, not here.
- **Name the source** in `source`, precisely enough for a reviewer to check it (a URL, or the
  catalogue edition and page).
- **One bullet, one entry.** Do not add a bullet again under a different name; correct the
  existing entry instead.
- **Keep the `id`** of an existing bullet when correcting it: apps use it to find the bullet.
  Mark bullets that are no longer made with `"discontinued": true` rather than deleting them.
- Pull requests that add advertising, links or made-up numbers are closed, and their
  authors blocked.

## Format

One file per maker, named after the maker in lowercase with `-` for anything that is not a
letter or a digit (`Sellier & Bellot` → `sellier-bellot.json`):

```json
{
  "maker": "Hornady",
  "bullets": [
    {
      "id": "hornady-eld-match-264-147",
      "name": "ELD Match",
      "diameter_in": 0.264,
      "weight_gr": 147,
      "bc": {
        "g1": 0.697,
        "g7": 0.351
      },
      "length_in": 1.43,
      "twist_in": 8,
      "source": {
        "type": "website",
        "ref": "https://www.hornady.com/bullets/rifle/6.5mm-.264-147-gr-eld-match"
      }
    }
  ]
}
```

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | `maker-name-diameter-weight` in lowercase, `-` between words, the leading `0.` of the diameter dropped and `_` for a decimal point in the weight. Never changes once published. |
| `name` | yes | The product name without the maker, caliber or weight: `ELD Match`, `Hybrid Target`. |
| `diameter_in` | yes | Bullet diameter, inches. |
| `weight_gr` | yes | Weight, grains. |
| `bc` | yes | Published ballistic coefficients, lb/in²: `g1`, `g7` or both. |
| `length_in` | no | Bullet length, inches. Used for stability and spin drift. |
| `twist_in` | no | Fastest twist the maker recommends, inches per turn. |
| `discontinued` | no | `true` for a bullet no longer made. |
| `source.type` | yes | `catalogue`, `website`, `box`, `doppler` or `dataset`. |
| `source.ref` | yes | URL, or catalogue edition and page. |
| `source.note` | no | Anything a reviewer should know. |

Before opening the pull request you can run the same checks as CI:

```bash
python3 tools/format.py     # sorts the entries and fixes the layout
python3 tools/validate.py   # errors fail the check; warnings are for the reviewer
```

## For reviewers

The check fails on broken files, missing fields, numbers outside physical limits and
duplicates. It warns about numbers that are possible but unusual: a G1/G7 ratio outside
1.6–2.4, a G7 that does not fit the bullet's sectional density, or a diameter no other bullet
has. Compare those with the source before merging.
