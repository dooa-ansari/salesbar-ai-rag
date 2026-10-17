# Clothes demo catalog

`products.csv` has 56 products (14 each of T-shirts, jeans, jackets, shoes). `build_csv.py` regenerates it. `images/` holds one SVG per product made by `../../images/make_images.py` (no AI calls).

## Columns

| Column | Meaning |
| --- | --- |
| id | Unique id (TS = T-shirt, JE = jeans, JA = jacket, SH = shoes). |
| name | Unique product name. |
| category | Display category. |
| image_type | Which drawing to use: tshirt, jeans, jacket, shoes. |
| brand | Brand name. |
| price, currency | Number and currency code. |
| colour | One colour word. |
| fit | Cut: skinny, slim, regular, straight, relaxed, wide or oversized. Empty means not recorded (all shoes, and the mystery tee and jeans). |
| season | summer, winter, spring_autumn or all_season. Empty means not recorded (SH14). |
| materials | Fabrics, separated by `\|`. **Empty means unknown** (treated as unsafe for material exclusions). |
| flags | Claims such as waterproof, organic_cotton, vegan, recycled, separated by `\|`. |
| free_from | Safety claims such as nickel_free, latex_free, separated by `\|`. |
| sizes_in_stock | `size:count` pairs separated by `\|`. Count 0 means sold out. Tops use S-XL, jeans W30-W36, shoes EU40-EU45. |
| description | One sentence used for the embedding. |
| image_url, product_url | Image path and product page path (placeholders). |

## Traps for the tests

- Wool: TS04, TS12, JE06, JA03, JA06, JA07, SH05.
- Sold out in a popular size: TS10 (M), JE10 (all), JE12 (W32), JA12 (M), SH10 (EU42).
- Just over a common budget: JA13 ($121, over $120), JA04 ($139).
- Near-identical pairs with different materials: TS02/TS03 (organic vs blend), JA02/JA03 (plain vs wool lining).
- Missing material data: TS14, JE14, JA14, SH14.

## Running query check

"waterproof jacket, size M, no wool, under $120" has exactly three exact matches: Trail Shell Jacket (JA01), Storm Rider Rain Jacket (JA02), Coast Rain Mac (JA05). Near matches: Alpine Rain Jacket (no M in stock), Harbor Rain Jacket ($1 over). Ruled out: JA03 and JA07 (wool), JA14 (material unknown), JA04 ($19 over, so near only if the ladder needs more).
