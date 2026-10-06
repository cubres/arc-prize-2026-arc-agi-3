"""Two ambiguous objects, one isolated anchor. All data are synthetic."""

import json

from correspondence import qualify_correspondence


def example_report():
    before = [{"id": "A", "bbox": [0, 0, 0, 0]},
              {"id": "B", "bbox": [2, 0, 2, 0]},
              {"id": "C", "bbox": [10, 0, 10, 0]}]
    after = [{"id": "U", "bbox": [1, -1, 1, -1]},
             {"id": "V", "bbox": [1, 1, 1, 1]},
             {"id": "W", "bbox": [10, 0, 10, 0]}]
    return qualify_correspondence(before, after, threshold2=0)


if __name__ == "__main__":
    print(json.dumps(example_report(), indent=2, sort_keys=True))
