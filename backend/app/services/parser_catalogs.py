"""
Catalog data used by the BibTeX parser.
"""

# Fields that should be extracted from BibTeX and promoted to columns
PROMOTED_FIELDS = {"title", "year", "file"}

# Required fields per entry type (BibTeX specification)
REQUIRED_FIELDS: dict[str, set[str]] = {
    "article": {"author", "title", "journal", "year"},
    "book": {"title", "publisher", "year"},
    "booklet": {"title"},
    "inbook": {"title", "publisher", "year"},
    "incollection": {"author", "title", "booktitle", "publisher", "year"},
    "inproceedings": {"author", "title", "booktitle", "year"},
    "manual": {"title"},
    "mastersthesis": {"author", "title", "school", "year"},
    "misc": set(),
    "phdthesis": {"author", "title", "school", "year"},
    "proceedings": {"title", "year"},
    "techreport": {"author", "title", "institution", "year"},
    "unpublished": {"author", "title", "note"},
}

# Venue normalization: slug -> (display_name, category, aliases)
VENUE_DATA: dict[str, tuple[str, str, list[str]]] = {
    "neurips": (
        "NeurIPS",
        "CONFERENCE",
        [
            "neurips",
            "nips",
            "advances in neural information processing systems",
            "neural information processing systems",
        ],
    ),
    "icml": (
        "ICML",
        "CONFERENCE",
        ["icml", "international conference on machine learning"],
    ),
    "iclr": (
        "ICLR",
        "CONFERENCE",
        ["iclr", "international conference on learning representations"],
    ),
    "cvpr": (
        "CVPR",
        "CONFERENCE",
        [
            "cvpr",
            "ieee/cvf conference on computer vision and pattern recognition",
            "computer vision and pattern recognition",
        ],
    ),
    "iccv": (
        "ICCV",
        "CONFERENCE",
        ["iccv", "ieee/cvf international conference on computer vision"],
    ),
    "eccv": ("ECCV", "CONFERENCE", ["eccv", "european conference on computer vision"]),
    "aaai": (
        "AAAI",
        "CONFERENCE",
        ["aaai", "aaai conference on artificial intelligence"],
    ),
    "ijcai": (
        "IJCAI",
        "CONFERENCE",
        ["ijcai", "international joint conference on artificial intelligence"],
    ),
    "acl": (
        "ACL",
        "CONFERENCE",
        ["acl", "annual meeting of the association for computational linguistics"],
    ),
    "emnlp": (
        "EMNLP",
        "CONFERENCE",
        ["emnlp", "empirical methods in natural language processing"],
    ),
    "naacl": (
        "NAACL",
        "CONFERENCE",
        [
            "naacl",
            "north american chapter of the association for computational linguistics",
        ],
    ),
    "aistats": (
        "AISTATS",
        "CONFERENCE",
        ["aistats", "artificial intelligence and statistics"],
    ),
    "uai": ("UAI", "CONFERENCE", ["uai", "uncertainty in artificial intelligence"]),
    "colt": ("COLT", "CONFERENCE", ["colt", "conference on learning theory"]),
    "kdd": ("KDD", "CONFERENCE", ["kdd", "knowledge discovery and data mining"]),
    "www": ("WWW", "CONFERENCE", ["www", "the web conference", "world wide web"]),
    "sigir": (
        "SIGIR",
        "CONFERENCE",
        ["sigir", "research and development in information retrieval"],
    ),
    "icra": (
        "ICRA",
        "CONFERENCE",
        ["icra", "ieee international conference on robotics and automation"],
    ),
    "iros": (
        "IROS",
        "CONFERENCE",
        ["iros", "ieee/rsj international conference on intelligent robots and systems"],
    ),
    "corl": ("CoRL", "CONFERENCE", ["corl", "conference on robot learning"]),
    "jmlr": ("JMLR", "JOURNAL", ["jmlr", "journal of machine learning research"]),
    "tmlr": ("TMLR", "JOURNAL", ["tmlr", "transactions on machine learning research"]),
    "nature": ("Nature", "JOURNAL", ["nature"]),
    "science": ("Science", "JOURNAL", ["science"]),
    "prl": ("PRL", "JOURNAL", ["prl", "physical review letters"]),
    "pre": ("PRE", "JOURNAL", ["pre", "physical review e"]),
    "prx": ("PRX", "JOURNAL", ["prx", "physical review x"]),
    "rmp": ("RMP", "JOURNAL", ["rmp", "reviews of modern physics"]),
    "pnas": (
        "PNAS",
        "JOURNAL",
        ["pnas", "proceedings of the national academy of sciences"],
    ),
    "tpami": (
        "TPAMI",
        "JOURNAL",
        ["tpami", "ieee transactions on pattern analysis and machine intelligence"],
    ),
    "neco": ("Neural Computation", "JOURNAL", ["neco", "neural computation"]),
    "tacl": (
        "TACL",
        "JOURNAL",
        ["tacl", "transactions of the association for computational linguistics"],
    ),
}

SUBJECT_PREFIXES: dict[str, str] = {
    "phy": "Physics",
    "cs": "Computer Science",
    "math": "Mathematics",
    "prog": "Programming",
    "stat": "Statistics",
    "bio": "Biology",
    "biology": "Biology",
    "chem": "Chemistry",
    "econ": "Economics",
    "eng": "Engineering",
    "neuro": "Neuroscience",
    "phil": "Philosophy",
}

FULL_SLUG_SUBJECTS: dict[str, str] = {
    "popular-science": "Popular Science",
    "science-fiction": "Science Fiction",
    "science-history": "History of Science",
    "self-help": "Self Help",
    "design": "Design",
    "engineering": "Engineering",
    "environment": "Environment",
    "philosophy": "Philosophy",
    "psychology": "Psychology",
    "writing": "Writing",
    "biology": "Biology",
}

CONTEXT_SUBAREA_NAMES: dict[str, str] = {
    "phy:general": "General Relativity",
    "phy:quantum": "Quantum Mechanics",
    "phy:statistical": "Statistical Mechanics",
    "phy:mathematical": "Mathematical Physics",
    "cs:general": "General",
    "cs:quantum": "Quantum Computing",
    "cs:os": "Operating Systems",
    "math:general": "General",
    "math:statistics": "Statistics",
    "prog:general": "General",
    "prog:design": "Software Design",
    "prog:languages": "Programming Languages",
}

SUBAREA_NAMES: dict[str, str] = {
    "ml": "Machine Learning",
    "ai": "Artificial Intelligence",
    "ml-ai": "Machine Learning & AI",
    "architecture": "Computer Architecture",
    "vision": "Computer Vision",
    "nlp": "Natural Language Processing",
    "graphics": "Graphics",
    "security": "Security",
    "networks": "Networks",
    "databases": "Databases",
    "systems": "Systems",
    "theory": "Theory",
    "classical": "Classical Mechanics",
    "field-theory": "Field Theory",
    "qft": "Quantum Field Theory",
    "condensed": "Condensed Matter",
    "particle": "Particle Physics",
    "astro": "Astrophysics",
    "electrodynamics": "Electrodynamics",
    "thermodynamics": "Thermodynamics",
    "relativity": "Relativity",
    "analysis": "Analysis",
    "algebra": "Algebra",
    "geometry": "Geometry",
    "topology": "Topology",
    "number-theory": "Number Theory",
    "information-theory": "Information Theory",
    "probability": "Probability",
    "combinatorics": "Combinatorics",
    "neuroscience": "Neuroscience",
    "algorithms": "Algorithms",
    "functional": "Functional Programming",
    "oop": "Object-Oriented Programming",
    "fp": "Functional Programming",
    "compilers": "Compilers",
}
