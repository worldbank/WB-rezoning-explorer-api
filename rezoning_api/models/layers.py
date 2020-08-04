from enum import Enum

LayerGroups = Enum("LayerGroups", [(lg, lg) for lg in ["distance", "gsa", "gwa"]])  # type: ignore
