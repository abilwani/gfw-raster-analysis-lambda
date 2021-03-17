from typing import List, Any, Set, Dict
from enum import Enum

from numpy import ndarray
from pydantic import BaseModel
from moz_sql_parser import parse

from raster_analysis.layer import Layer
from raster_analysis.data_lake import LAYERS
from raster_analysis.exceptions import QueryParseException


class SpecialSelectors(str, Enum):
    latitude = "latitude"
    longitude = "longitude"
    area__ha = "area__ha"
    value__count = "value__count"


class Operator(str, Enum):
    gt = ">"
    lt = "<"
    gte = ">="
    lte = "<="
    eq = "=="
    neq = "!="


class Filter(BaseModel):
    operator: Operator
    layer: Layer
    value: Any

    def apply_filter(self, window: ndarray) -> ndarray:
        if self.layer.is_conf_encoded:
            window = window % 10000

        return eval(f"window {self.operator.value} self.value")


class AggregateFunction(str, Enum):
    sum = "sum"
    avg = "avg"


class Aggregate(BaseModel):
    function: AggregateFunction
    layer: Layer


class Query(BaseModel):
    selectors: List[Layer] = []
    filters: List[Filter] = []
    groups: List[Layer] = []
    aggregates: List[Aggregate] = []

    def get_real_layers(self) -> List[Layer]:
        layers = self.get_layers()
        return [layer for layer in layers if layer.layer not in SpecialSelectors]

    def get_layers(self) -> List[Layer]:
        layers = [selector for selector in self.selectors]
        layers += [filter.layer for filter in self.filters]
        layers += [aggregate.layer for aggregate in self.aggregates]
        layers += [group for group in self.groups]

        return list(dict.fromkeys(layers))

    def get_result_layers(self) -> List[Layer]:
        layers = [selector for selector in self.selectors]
        layers += [aggregate.layer for aggregate in self.aggregates]
        layers += [group for group in self.groups]

        return list(dict.fromkeys(layers))

    def get_group_columns(self) -> List[str]:
        return [group.layer for group in self.groups]

    @staticmethod
    def parse_query(raw_query: str):
        parsed = parse(raw_query)
        query = Query()

        if "select" not in parsed:
            raise QueryParseException("Query be SELECT statement")

        for selector in Query._ensure_list(parsed["select"]):
            if isinstance(selector["value"], dict):
                func, layer = Query._get_first_key_value(selector["value"])
                aggregate = Aggregate(function=func, layer=LAYERS[layer])
                query.aggregates.append(aggregate)
            elif isinstance(selector["value"], str):
                query.selectors.append(LAYERS[selector["value"]])

        if "where" in parsed:
            if "and" in parsed["where"]:
                if isinstance(parsed["where"]["and"], dict):
                    raise QueryParseException(
                        "Only one level is supported in AND statement."
                    )
                filters = parsed["where"]["and"]
            elif "or" in parsed["where"]:
                raise QueryParseException("OR statement is not supported.")
            else:
                filters = parsed["where"]

            for filter in Query._ensure_list(filters):
                op, (layer, value) = Query._get_first_key_value(filter)
                if isinstance(value, dict):
                    value = value["literal"]

                layer = LAYERS[layer]
                if layer.encoder:
                    for enc_val in layer.encoder(value):
                        query.filters.append(
                            Filter(operator=Operator[op], layer=layer, value=enc_val)
                        )
                else:
                    query.filters.append(
                        Filter(operator=Operator[op], layer=layer, value=value)
                    )

        if "groupby" in parsed:
            for group in Query._ensure_list(parsed["groupby"]):
                query.groups.append(LAYERS[group["value"]])

        return query

    # the SQL parser sometimes outputs a list or single value depending on input,
    # Just a helper to make it consistent
    def _ensure_list(a):
        return a if type(a) is list else [a]

    # certain things are parsed single key value pairs, so just get the first key value pair
    def _get_first_key_value(d: Dict[str, str]):
        for key, val in d.items():
            return (key, val)
