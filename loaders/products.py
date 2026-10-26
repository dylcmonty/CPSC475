"""The product lexicon and the rules that match auction labels to it.

Each product is something the auctions sell, tied to the plant taxon it
comes from (a species, or a genus when the reports do not say which
species). Several products can share a taxon: broccoli, cabbage and
kale are all Brassica oleracea.

match() maps one auction label to a product slug, or None. Labels that
match nothing (hanging baskets, honey, metal art, uncommon flowers) stay
unresolved; Advanced Function 3 is the tool for those.

Most scientific names are looked up in the GBIF backbone. GBIF lumps the
cabbage crops (and bok choy, shallots, nectarines) into their species,
so those products sit under the cultivar groups named in CULTIVAR_GROUPS,
which follow the International Code of Nomenclature for Cultivated Plants.
"""
import re

# slug: (title, scientific name, common name)
PRODUCTS = {
    # Produce
    "apples": ("Apples", "Malus domestica", "apple"),
    "asparagus": ("Asparagus", "Asparagus officinalis", "asparagus"),
    "green-beans": ("Green beans", "Phaseolus vulgaris", "common bean"),
    "beets": ("Beets", "Beta vulgaris subsp. vulgaris", "beet"),
    "blackberries": ("Blackberries", "Rubus allegheniensis", "blackberry"),
    "black-raspberries": ("Black raspberries", "Rubus occidentalis", "black raspberry"),
    "raspberries": ("Raspberries", "Rubus idaeus", "red raspberry"),
    "blueberries": ("Blueberries", "Vaccinium corymbosum", "highbush blueberry"),
    "strawberries": ("Strawberries", "Fragaria ananassa", "garden strawberry"),
    "bok-choy": ("Bok choy", "Brassica rapa Chinensis Group", "bok choy"),
    "broccoli": ("Broccoli", "Brassica oleracea Italica Group", "broccoli"),
    "cabbage": ("Cabbage", "Brassica oleracea Capitata Group", "cabbage"),
    "cauliflower": ("Cauliflower", "Brassica oleracea Botrytis Group", "cauliflower"),
    "kale": ("Kale", "Brassica oleracea Sabellica Group", "kale"),
    "kohlrabi": ("Kohlrabi", "Brassica oleracea Gongylodes Group", "kohlrabi"),
    "brussels-sprouts": ("Brussels sprouts", "Brassica oleracea Gemmifera Group", "Brussels sprouts"),
    "collard-greens": ("Collard greens", "Brassica oleracea Viridis Group", "collards"),
    "cantaloupes": ("Cantaloupes", "Cucumis melo subsp. melo", "muskmelon"),
    "watermelons": ("Watermelons", "Citrullus lanatus", "watermelon"),
    "carrots": ("Carrots", "Daucus carota", "carrot"),
    "celery": ("Celery", "Apium graveolens var. dulce", "celery"),
    "cherries": ("Cherries", "Prunus avium", "sweet cherry"),
    "ground-cherries": ("Ground cherries", "Physalis pruinosa", "ground cherry"),
    "sweet-corn": ("Sweet corn", "Zea mays subsp. mays", "corn"),
    "ornamental-corn": ("Ornamental corn", "Zea mays subsp. mays", "corn"),
    "cucumbers": ("Cucumbers", "Cucumis sativus", "cucumber"),
    "pickling-cucumbers": ("Pickling cucumbers", "Cucumis sativus", "cucumber"),
    "dill": ("Dill", "Anethum graveolens", "dill"),
    "parsley": ("Parsley", "Petroselinum crispum", "parsley"),
    "cilantro": ("Cilantro", "Coriandrum sativum", "coriander"),
    "basil": ("Basil", "Ocimum basilicum", "sweet basil"),
    "eggplant": ("Eggplant", "Solanum melongena", "eggplant"),
    "garlic": ("Garlic", "Allium sativum", "garlic"),
    "onions": ("Onions", "Allium cepa", "onion"),
    "green-onions": ("Green onions", "Allium cepa", "onion"),
    "shallots": ("Shallots", "Allium cepa Aggregatum Group", "shallot"),
    "leeks": ("Leeks", "Allium ampeloprasum", "leek"),
    "grapes": ("Grapes", "Vitis labrusca", "fox grape"),
    "lettuce": ("Lettuce", "Lactuca sativa", "lettuce"),
    "okra": ("Okra", "Abelmoschus esculentus", "okra"),
    "peaches": ("Peaches", "Prunus persica", "peach"),
    "nectarines": ("Nectarines", "Prunus persica Nucipersica Group", "nectarine"),
    "pears": ("Pears", "Pyrus communis", "pear"),
    "plums": ("Plums", "Prunus domestica", "plum"),
    "peas": ("Peas", "Pisum sativum", "garden pea"),
    "bell-peppers": ("Bell peppers", "Capsicum annuum var. annuum", "pepper"),
    "hot-peppers": ("Hot peppers", "Capsicum annuum var. annuum", "pepper"),
    "peppers": ("Peppers", "Capsicum annuum var. annuum", "pepper"),
    "potatoes": ("Potatoes", "Solanum tuberosum", "potato"),
    "sweet-potatoes": ("Sweet potatoes", "Ipomoea batatas", "sweet potato"),
    "pumpkins": ("Pumpkins", "Cucurbita pepo subsp. pepo", "pumpkin"),
    "ornamental-gourds": ("Ornamental gourds", "Cucurbita pepo", "field pumpkin"),
    "zucchini": ("Zucchini", "Cucurbita pepo subsp. pepo", "pumpkin"),
    "summer-squash": ("Summer squash", "Cucurbita pepo", "field pumpkin"),
    "acorn-squash": ("Acorn squash", "Cucurbita pepo", "field pumpkin"),
    "spaghetti-squash": ("Spaghetti squash", "Cucurbita pepo", "field pumpkin"),
    "butternut-squash": ("Butternut squash", "Cucurbita moschata", "crookneck pumpkin"),
    "hubbard-squash": ("Hubbard and turban squash", "Cucurbita maxima", "winter squash"),
    "cushaw": ("Cushaw", "Cucurbita argyrosperma", "cushaw"),
    "squash": ("Squash, mixed or unnamed", "Cucurbita", None),
    "radishes": ("Radishes", "Raphanus sativus", "radish"),
    "rhubarb": ("Rhubarb", "Rheum rhabarbarum", "rhubarb"),
    "spinach": ("Spinach", "Spinacia oleracea", "spinach"),
    "tomatoes": ("Tomatoes", "Solanum lycopersicum", "tomato"),
    "cherry-tomatoes": ("Cherry and grape tomatoes", "Solanum lycopersicum", "tomato"),
    "tomato-plants": ("Tomato plants", "Solanum lycopersicum", "tomato"),
    "pepper-plants": ("Pepper plants", "Capsicum annuum var. annuum", "pepper"),
    # Flowers and nursery stock
    "mums": ("Mums", "Chrysanthemum morifolium", "florist's daisy"),
    "sunflowers": ("Sunflowers", "Helianthus annuus", "common sunflower"),
    "zinnias": ("Zinnias", "Zinnia elegans", "zinnia"),
    "marigolds": ("Marigolds", "Tagetes erecta", "Mexican marigold"),
    "petunias": ("Petunias", "Petunia", None),
    "geraniums": ("Geraniums", "Pelargonium", None),
    "begonias": ("Begonias", "Begonia", None),
    "celosia": ("Celosia", "Celosia argentea", "silver cock's comb"),
    "coneflowers": ("Coneflowers", "Echinacea purpurea", "purple coneflower"),
    "lavender": ("Lavender", "Lavandula angustifolia", "English lavender"),
    "hibiscus": ("Hibiscus", "Hibiscus", None),
    "dahlias": ("Dahlias", "Dahlia", None),
    "impatiens": ("Impatiens", "Impatiens walleriana", "busy Lizzie"),
    "coleus": ("Coleus", "Coleus scutellarioides", "coleus"),
    "roses": ("Roses", "Rosa", None),
    "hollyhocks": ("Hollyhocks", "Alcea rosea", "hollyhock"),
    "gerbera-daisies": ("Gerbera daisies", "Gerbera jamesonii", "Barberton daisy"),
    "pansies": ("Pansies", "Viola", None),
    "asters": ("Asters", "Symphyotrichum", None),
    "lilies": ("Lilies", "Lilium", None),
    "azaleas": ("Azaleas", "Rhododendron", None),
    "boxwood": ("Boxwood", "Buxus sempervirens", "common box"),
    "arborvitae": ("Arborvitae", "Thuja occidentalis", "northern white cedar"),
    "hostas": ("Hostas", "Hosta", None),
    "peonies": ("Peonies", "Paeonia lactiflora", "Chinese peony"),
    "hydrangeas": ("Hydrangeas", "Hydrangea macrophylla", "bigleaf hydrangea"),
    "dianthus": ("Dianthus", "Dianthus", None),
    "rudbeckia": ("Black-eyed Susans", "Rudbeckia hirta", "black-eyed Susan"),
}

# Cultivar groups (ICNCP) placed under their species: name -> species.
CULTIVAR_GROUPS = {
    "Brassica oleracea Capitata Group": "Brassica oleracea",
    "Brassica oleracea Italica Group": "Brassica oleracea",
    "Brassica oleracea Botrytis Group": "Brassica oleracea",
    "Brassica oleracea Gongylodes Group": "Brassica oleracea",
    "Brassica oleracea Gemmifera Group": "Brassica oleracea",
    "Brassica oleracea Sabellica Group": "Brassica oleracea",
    "Brassica oleracea Viridis Group": "Brassica oleracea",
    "Brassica rapa Chinensis Group": "Brassica rapa",
    "Allium cepa Aggregatum Group": "Allium cepa",
    "Prunus persica Nucipersica Group": "Prunus persica",
}

# Misspellings that appear in the reports.
TYPOS = {
    "sqaush": "squash", "pumkins": "pumpkins", "pumkin": "pumpkin",
    "canataloupes": "cantaloupes", "cantaloups": "cantaloupes", "cucmbers": "cucumbers",
    "poatoes": "potatoes", "potatos": "potatoes", "brocolli": "broccoli", "onios": "onions",
    "pickels": "pickles", "pepeprs": "peppers", "pepers": "peppers", "begonnia": "begonia",
    "lavendar": "lavender", "impatients": "impatiens", "azalae": "azalea", "brussel": "brussels",
    "spouts": "sprouts", "radished": "radishes", "diakon": "daikon", "cornsweet": "corn sweet",
    "onionsdry": "onions dry", "onionsgreen": "onions green", "beansbeans": "beans",
    "blackraspberries": "black raspberries", "redraspberries": "red raspberries",
    "susie": "susan", "susies": "susan",
}

# Words whose trailing s is not a plural.
KEEP_S = {"asparagus", "hibiscus", "impatiens", "sunpatiens", "brussels", "dianthus",
          "cactus", "grass", "citrus", "crocus", "coleus", "celosia", "lupinus"}

NOT_PLANTS = {"syrup", "art", "metal", "wood", "firewood", "straw", "bale", "salt",
              "egg", "soap", "candle", "stalk", "decor", "wreath", "sign", "bench", "mushroom"}
MIXED = {"basket", "planter", "combo", "mix", "mixed", "assorted", "misc", "miscellaneou",
         "seasonal"}
# Words that mark a young plant rather than the crop; the unit is part of the label.
PLANT_STARTS = {"plant", "cont", "container", "start", "pot", "cell", "pack", "tray"}


def normalize(text):
    """Lowercase, punctuation to spaces, single spaces: the label_norm key."""
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())


def stems(label):
    words = []
    for word in normalize(label).split():
        word = TYPOS.get(word, word)
        for part in word.split():
            if part in KEEP_S:
                words.append(part)
            elif part.endswith(("ches", "shes", "xes", "sses", "oes")):
                words.append(part[:-2])
            elif part.endswith("ies"):
                words.append(part[:-3] + "y")
            elif part.endswith("s") and not part.endswith("ss"):
                words.append(part[:-1])
            else:
                words.append(part)
    return set(words)


# Ordered rules: (product slug, words that must all appear, words that must not).
RULES = [
    ("sweet-potatoes", {"sweet", "potato"}, set()),
    ("ground-cherries", {"ground", "cherry"}, set()),
    ("black-raspberries", {"black", "raspberry"}, set()),
    ("ornamental-corn", {"ornamental", "corn"}, set()),
    ("ornamental-gourds", {"gourd"}, set()),
    ("cherry-tomatoes", {"tomato", "cherry"}, set()),
    ("cherry-tomatoes", {"tomato", "grape"}, set()),
    ("tomatoes", {"tomato"}, set()),
    ("green-onions", {"onion", "green"}, set()),
    ("green-onions", {"scallion"}, set()),
    ("onions", {"onion"}, set()),
    ("shallots", {"shallot"}, set()),
    ("garlic", {"garlic"}, set()),
    ("leeks", {"leek"}, set()),
    ("bell-peppers", {"pepper", "bell"}, set()),
    ("hot-peppers", {"pepper", "hot"}, set()),
    ("hot-peppers", {"pepper", "jalapeno"}, set()),
    ("hot-peppers", {"pepper", "banana"}, set()),
    ("hot-peppers", {"pepper", "cayenne"}, set()),
    ("hot-peppers", {"pepper", "habanero"}, set()),
    ("peppers", {"pepper"}, set()),
    ("zucchini", {"zucchini"}, set()),
    ("butternut-squash", {"butternut"}, set()),
    ("hubbard-squash", {"hubbard"}, set()),
    ("hubbard-squash", {"turban"}, set()),
    ("hubbard-squash", {"buttercup"}, set()),
    ("hubbard-squash", {"kabocha"}, set()),
    ("cushaw", {"cushaw"}, set()),
    ("acorn-squash", {"acorn"}, set()),
    ("spaghetti-squash", {"spaghetti"}, set()),
    ("summer-squash", {"squash", "yellow"}, set()),
    ("summer-squash", {"squash", "patty"}, set()),
    ("summer-squash", {"squash", "crookneck"}, set()),
    ("squash", {"squash"}, set()),
    ("pumpkins", {"pumpkin"}, set()),
    ("cantaloupes", {"cantaloupe"}, set()),
    ("cantaloupes", {"aphrodite"}, set()),
    ("cantaloupes", {"sugarcube"}, set()),
    ("cantaloupes", {"goddess"}, set()),
    ("watermelons", {"watermelon"}, set()),
    ("pickling-cucumbers", {"pickle"}, set()),
    ("cucumbers", {"cucumber"}, set()),
    ("sweet-corn", {"corn"}, {"pop", "popcorn"}),
    ("green-beans", {"bean"}, {"lima", "dry"}),
    ("beets", {"beet"}, set()),
    ("blackberries", {"blackberry"}, set()),
    ("raspberries", {"raspberry"}, set()),
    ("blueberries", {"blueberry"}, set()),
    ("strawberries", {"strawberry"}, set()),
    ("bok-choy", {"bok"}, set()),
    ("brussels-sprouts", {"brussels"}, set()),
    ("broccoli", {"broccoli"}, set()),
    ("cauliflower", {"cauliflower"}, set()),
    ("cabbage", {"cabbage"}, set()),
    ("kohlrabi", {"kohlrabi"}, set()),
    ("collard-greens", {"collard"}, set()),
    ("kale", {"kale"}, {"ornamental"}),
    ("carrots", {"carrot"}, set()),
    ("celery", {"celery"}, set()),
    ("cherries", {"cherry"}, set()),
    ("apples", {"apple"}, set()),
    ("apples", {"honeycrisp"}, set()),
    ("asparagus", {"asparagus"}, set()),
    ("dill", {"dill"}, set()),
    ("parsley", {"parsley"}, set()),
    ("cilantro", {"cilantro"}, set()),
    ("basil", {"basil"}, set()),
    ("eggplant", {"eggplant"}, set()),
    ("grapes", {"grape"}, set()),
    ("lettuce", {"lettuce"}, set()),
    ("okra", {"okra"}, set()),
    ("nectarines", {"nectarine"}, set()),
    ("peaches", {"peach"}, set()),
    ("pears", {"pear"}, set()),
    ("plums", {"plum"}, set()),
    ("peas", {"pea"}, set()),
    ("potatoes", {"potato"}, set()),
    ("radishes", {"radish"}, set()),
    ("radishes", {"daikon"}, set()),
    ("rhubarb", {"rhubarb"}, set()),
    ("spinach", {"spinach"}, set()),
    ("mums", {"mum"}, set()),
    ("sunflowers", {"sunflower"}, set()),
    ("zinnias", {"zinnia"}, set()),
    ("marigolds", {"marigold"}, set()),
    ("petunias", {"petunia"}, set()),
    ("geraniums", {"geranium"}, set()),
    ("begonias", {"begonia"}, set()),
    ("celosia", {"celosia"}, set()),
    ("celosia", {"coxcomb"}, set()),
    ("coneflowers", {"coneflower"}, set()),
    ("lavender", {"lavender"}, set()),
    ("hibiscus", {"hibiscus"}, set()),
    ("dahlias", {"dahlia"}, set()),
    ("impatiens", {"impatiens"}, set()),
    ("coleus", {"coleus"}, set()),
    ("roses", {"rose"}, set()),
    ("hollyhocks", {"hollyhock"}, set()),
    ("gerbera-daisies", {"gerbera"}, set()),
    ("pansies", {"pansy"}, set()),
    ("asters", {"aster"}, set()),
    ("lilies", {"lily"}, {"canna", "calla"}),
    ("azaleas", {"azalea"}, set()),
    ("boxwood", {"boxwood"}, set()),
    ("arborvitae", {"arborvitae"}, set()),
    ("hostas", {"hosta"}, set()),
    ("peonies", {"peony"}, set()),
    ("hydrangeas", {"hydrangea"}, set()),
    ("dianthus", {"dianthus"}, set()),
    ("rudbeckia", {"rudbeckia"}, set()),
    ("rudbeckia", {"black", "eyed", "susan"}, set()),
]

# Produce that is also sold as a young plant in a pot or flat.
PLANT_START_PRODUCTS = {"tomatoes": "tomato-plants", "cherry-tomatoes": "tomato-plants",
                        "peppers": "pepper-plants", "bell-peppers": "pepper-plants",
                        "hot-peppers": "pepper-plants"}


def match(label):
    """The product slug for an auction label, or None if it should stay unresolved."""
    words = stems(label)
    if words & NOT_PLANTS or words & MIXED:
        return None
    for slug, need, avoid in RULES:
        if need <= words and not words & avoid:
            break
    else:
        return None
    plant_start = bool(words & PLANT_STARTS)
    produce = slug in PRODUCTS and list(PRODUCTS).index(slug) < list(PRODUCTS).index("mums")
    if plant_start and produce:
        # A berry or herb plant is not a price for the fruit; only tomato and
        # pepper plants are common enough to be products of their own.
        return PLANT_START_PRODUCTS.get(slug)
    return slug
