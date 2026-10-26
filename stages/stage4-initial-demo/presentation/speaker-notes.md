# Speaker Notes

Notes for each slide in `slides.pdf`, in order.

## 1. Almanac

Introduce the team and the project in one sentence: Almanac is a farm record book where every entry is tied to a plant taxonomy, and that same taxonomy indexes eight seasons of real Ohio produce auction prices. Plan for about 1 minute of slides, 4 minutes of live demo, 1 to 2 minutes on the advanced-function plan.

## 2. Three kinds of data, one shared key

Farm software like Tend or Farmbrite keeps records but has no prices and treats crops as free text. USDA Market News and auction reports have prices but no connection to any farm. Plant databases have taxonomy but neither. Almanac joins all three on the taxon, so a grower can ask what a crop they just harvested is worth and get the answer from one query.

## 3. Collected, cleaned and loaded

Our scripts in loaders/ download every USDA Market News report for the Mount Hope Auction (2019 to 2026) and every County Line Produce Auction market report PDF (2024 to 2026), pull out every price line, convert prices to whole cents, standardize 237 unit spellings to 35 units, and normalize the description. The taxonomy is from the GBIF Backbone Taxonomy; farms are named Ohio farms, farm markets and orchards from OpenStreetMap, with counties from the US Census. Rows that break a CHECK constraint are not dropped and the constraint is not loosened: 26 went to market_lot_quarantine. Example: a cabbage line listed low $1.10, high $2.10, average $19.50. The 1,445 unmatched labels (4,795 prices) are what Advanced Function 3 will fix. Grower data (plots, catalog, events) comes from real users once the site is public in November.

## 4. 12 tables, 15 foreign keys, 2 views

Why PostgreSQL: the advanced functions need recursive CTEs and window functions. Every user value is a bound parameter, never pasted into SQL, so SQL injection is not possible. Data rules are CHECK constraints and foreign key actions, not application code, so they hold no matter which page writes. The app turns a constraint violation into a plain message for the user.

## 5. The basic functions, in the app

Switch to the browser here. Follow the demo script (demo-script.md). Target about 4 minutes. Have the browser tabs open and logged in before the talk starts.

## 6. Four queries, four questions

Explain the join. It matches on taxon_id, not on names, so a harvest recorded as Allium cepa finds every onion lot however the auction worded it. Only event kinds with is_yield = true count as harvests. The window is the harvest date plus or minus 30 days.

## 7. Three things no farm app can do

1: The user can start at any rank and the number of levels below it varies, so a fixed number of joins cannot do it. The recursive CTE walks the subtree in one round trip. Already tested: Asparagales walks 305 nodes, finds 6 priced taxa, 1,805 prices; the biggest group is onion by the peck, 558 prices at an $8.62 mean. 2: Day-of-year window across years, compared within one unit, at least 12 lots in 2 or more years, score = mean divided by (1 + coefficient of variation), ranked with RANK() OVER. Every candidate must resolve to a taxon, which keeps honey, firewood and metal art out of the ranking. Tested: late April across all plants gives 18 product-and-unit candidates led by marigolds by the flat, azaleas each and tomato plants by the flat; rooted at Asparagales it gives one, asparagus. 3: The loaders already fetch and parse new reports by the shape of each line, not fixed columns; the ladder takes their unmatched labels. Four rungs from exact slug down to scientific name. One candidate binds, zero falls through, more than one stops as ambiguous. A person confirms every match. Measured by the coverage percentage going up.

## 8. From here to the final demo

The site goes public at least a week before the final presentation, as the assignment requires, and we will email Dr. Cheng when it is live. Dylan: Advanced Functions 1 and 2, database, deployment. Andrew: Advanced Function 3 and the review screen, search pages, recruiting users.

## 9. Questions?

Likely questions. Why is the roll-up advanced? Unknown depth: needs a recursive CTE, not a fixed number of joins. Why not match labels by substring? "Wild garlic" is not garlic, and two equal matches must not be resolved by whichever row comes first. Where does grower data come from? Real users after the site goes public on Nov 9. How do you stop SQL injection? Every value is a bound parameter.
