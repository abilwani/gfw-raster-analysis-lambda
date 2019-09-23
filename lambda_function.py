from raster_analysis import geoprocessing
from raster_analysis.geoprocessing import Filter
from shapely.geometry import shape

import sys
import json

BASE_URL = "/vsis3/gfw-files/2018_update/{raster_id}/{tile_id}.tif"


def serialize(func):
    def wrapper(*args, **kwargs):
        try:
            body = func(*args, **kwargs)
            result = {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": body,
            }
        except ValueError as e:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": {"message": e},
            }
        except Exception as e:
            result = {
                "statusCode": 500,
                "headers": {"Content-Type": "application/json"},
                "body": {"message": e},
            }

        return json.dumps(result)

    return wrapper


@serialize
def lambda_handler(event, context):
    missing_required_params = []
    if "analysis_raster_id" not in event:
        missing_required_params.append("analysis_raster_id")
    elif "geometry" not in event:
        missing_required_params.append("geometry")

    if missing_required_params:
        raise ValueError("Missing parameters: " + ", ".join(missing_required_params))

    analysis_raster_id = event["analysis_raster_id"]
    contextual_raster_ids = event["contextual_raster_ids"]
    aggregate_raster_ids = (
        event["aggregate_raster_ids"] if "aggregate_raster_ids" in event else []
    )
    analysis = event["analysis"]
    geometry = shape(event["geometry"])

    if analysis not in ["area", "sum", "count"]:
        raise ValueError("Unknown analysis: " + analysis)

    filters = [Filter(**f) for f in event["filters"]] if "filters" in event else []

    return geoprocessing.analysis(
        geometry,
        analysis_raster_id,
        contextual_raster_ids,
        aggregate_raster_ids,
        filters,
        analysis,
    )


if __name__ == "__main__":
    # "{\"analysis_raster_id\":\"loss\", \"contextual_raster_ids\":[\"wdpa\"], \"aggregate_raster_ids\":[\"tcd_2000\", \"tcd_2010\"], \"analysis\":\"sum\", \"geometry\":{\"type\":\"Polygon\",\"coordinates\":[[[9.0,4.1],[9.1,4.1],[9.1,4.2],[9.0,4.2],[9.0,4.1]]]},\"filters\":[{\"raster_id\":\"tcd_2000\",\"threshold\":30}]}"), None))
    print(lambda_handler(json.loads(sys.argv[1]), None))
