# The Harvest and the Hunt

*Harvest the work. Hunt the gap.*

The *harvest* is the everyday work of feeding and running a home, the labour this project measures. The *hunt* is tracking down the gap between what people say and what they do.

**Question:** among people who say they support women working, how many live in households where the housework is actually shared? Measured across [N] countries with ISSP 2022 survey data, plus a local-first tool that shows one household its own split.

**Status:** Session 1 of 5 done. Definitions are fixed and the cleaning runs on the real data (27,392 partnered respondents in 32 countries); results are not in yet.

## Data

ISSP Research Group (2025). *International Social Survey Programme: Family and Changing Gender Roles V - ISSP 2022.* GESIS Data Archive, Cologne. ZA10000 Data file Version 2.0.0, https://doi.org/10.4232/5.ZA10000.2.0.0

The data can't be redistributed. To reproduce: register at GESIS, download the Stata file (`ZA10000_v2-0-0.dta`), put it in `data/raw/`, then run:

```
python scripts/build_sample.py data/raw/ZA10000_v2-0-0.dta
```

Sample sizes per country: [results/sample_flow.csv](results/sample_flow.csv). Variable list: [variables.md](variables.md).

Definitions: [definitions.md](definitions.md).

## Run the tests

```
pip install -e ".[dev]"
pytest
```

## Prior work

- ISSP Research Group, Family and Changing Gender Roles modules (1988–2022).
- International Labour Organization (2018), *Care Work and Care Jobs for the Future of Decent Work.*
- Bursztyn et al., *How Are Gender Norms Perceived?*

Nothing here is advice about any particular household. Findings are associations, not causes.
