# Ballistics bullets

An open database of rifle bullets for ballistic calculators: diameter, weight,
published ballistic coefficients (G1, G7), length and recommended twist, each with
its source.

It is the bullet library of the [KGW Labs Ballistics](https://github.com/krzysztofgw-pl/ballistics-calculator)
app, but any app may use it under the licence below.

## Using the data

- Source files: [`bullets/`](bullets), one JSON file per maker.
- Ready-made bundle with every bullet in one file, rebuilt on every change:
  `https://krzysztofgw-pl.github.io/ballistics-bullets/v1/bullets.json`

```json
{
  "format": 1,
  "version": 1793390000,
  "commit": "a1b2c3d",
  "bullets": [
    {
      "maker": "Hornady", "id": "hornady-eld-match-264-147", "name": "ELD Match",
      "diameter_in": 0.264, "weight_gr": 147, "bc": {"g1": 0.697, "g7": 0.351},
      "length_in": 1.43, "source": {"type": "catalogue", "ref": "..."}
    }
  ]
}
```

`version` only grows, so an app can keep the newest bundle it has seen. A change the
format-1 readers cannot handle will be published under `v2/`, and `v1/` keeps working.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). In short: open a pull request that edits a file in
`bullets/` and says where the numbers come from, or suggest a bullet from inside the app.
Every change is reviewed before it is published.

## Licence

The data is licensed under [CC BY-SA 4.0](LICENSE): you may use and share it, also
commercially, if you credit this project and share changes to the data under the same licence.

The first version was imported from the app's library, which was compiled from the
[ammolytics/projectiles](https://github.com/ammolytics/projectiles) dataset (MIT, see
[NOTICE](NOTICE)), the Berger 2024 catalogue and manufacturers' websites.

The scripts in `tools/` are MIT-licensed.

Ballistic coefficients are the manufacturers' published figures. They change between
catalogue editions and between lots; always check them against your own drops.
