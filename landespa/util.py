import pyproj
from shapely import geometry
from usgs import soap, api
import requests
import re
from datetime import datetime
from pprint import pprint

# Parameter
# Coordinates of a point (flux tower) in decimal degrees
center_long = 12
center_lat = 45
start_date='2015-04-01'
end_date='2016-05-01'
# radius in meters, used to defined the extent around the supplied origin
radius = 2000
user_name = 'dutrieux'
password = 'passwd'
# Get your own api key using "usgs login usgs_username usgs_password" directly from the command line
api_key = '233009bd81ee4aa3b48169a7c1dd3a78'

def xyToBox(long, lat):
    # Define an extent around the point (requires projecting back and forth to a
    # equidistant local projection
    prj = pyproj.Proj(proj='aeqd', lat_0=center_lat, lon_0=center_long)
    box = geometry.box(-radius, -radius, radius, radius)
    # Project back to longlat
    lngs, lats = prj(*box.exterior.xy, inverse=True)

    # Reformat to 2 dictionaries
    ll = { "longitude": min(*lngs), "latitude": min(*lats) }
    ur = { "longitude": max(*lngs), "latitude": max(*lats) }
    return (ll, ul, lngs, lats)

def querySceneLists(collections, ll, ur, start_date, end_date, api_key):
    # Init a dictionary to store sceneLists for each sensor
    scene_list_dict = {}
    for collection in collections:
        # Query sceneList
        scenes = api.search(collection['ee'], 'EE',\
            ll=ll,\
            ur=ur,\
            start_date=start_date,\
            end_date=end_date,\
            api_key=api_key)

        scene_list = []
        for scene in scenes:
            scene_list.append(scene['entityId'])
        # Apend dictonary that contains all sceneLists for all sensors
        scene_list_dict[collection['espa']] = scene_list

    return scene_list_dict



def parseSceneId(id):
    """Landsat sceneID parser

    Identifies a typical LandsatID sequence in a string and returns a
    dictionary with information on sensor, date, path and row. The function
    raises an error in case no Landsat scene ID pattern can be found

    Args:
        id (string) string containing a Landsat scene ID

    Returns:
        dictionary: Dictionary containing information on sensor, date, path and row
    """
    id_grep = re.compile(".*(LT4|LT5|LE7|LC8)(\d{3})(\d{3})(\d{7}).*", re.IGNORECASE)
    m = id_grep.search(id)
    if m is None:
        raise ValueError('Landsat ID pattern not found for %s' % id)
    id_meta = {'sensor': m.group(1).upper(),
               'date': datetime.strptime(m.group(4), "%Y%j").date(),
               'path': int(m.group(2)),
               'row': int(m.group(3))}
    return id_meta


class jsonBuilder(object):
    """Class to incrementaly build a dictionary passed as json to the espa order"""
    def __init__(self, sensor, scene_list,\
        products = ["sr", "sr_ndvi", "cloud", "sr_ndmi", "sr_evi", "sr_savi"],\
        note = "Order passed on %s" % datetime.strftime(datetime.now(), '%Y-%m-%d %H:%M:%S')):
        """
        Args:
            sensor (string) one of tm4, tm5, etm7, oli8
            scene_list (list) list of sceneIDs
            products (list of strings)
            note (string)
        """
        if sensor not in ['tm4', 'tm5', 'etm7', 'oli8']:
            raise ValueError('Invalid sensor (chose between tm4, tm5, etm7 and oli8)')
        self.process_dict = {
            sensor : {
            "inputs": scene_list, 
            "products": products
        },
            "format": "gtiff",
            "note": note
        }
    def addProjection(self, proj = 'aea', resampling_method = 'bil', center_coords = None):
        """
        Args:
            proj (string)
            resampling_method (string)
            center_coords (dict) Required for proj = 'aea' only. Dict with long and lat keys
        """
        if proj is 'aea':
            if center_coords is None:
                raise ValueError('With aea projection you must supply a dictionary of center coordinates')
            proj_dict = {"projection": {
                            "aea": {
                                "standard_parallel_1": center_coords['lat'] - 5,
                                "standard_parallel_2": center_coords['lat'] + 5,
                                "central_meridian": center_coords['long'],
                                "latitude_of_origin": center_coords['lat'],
                                "false_easting": 0.0,
                                "false_northing": 0.0,
                                "datum": "wgs84"
                            }
                        },
                        "resampling_method": resampling_method}
        else:
            raise ValueError('Projection not yet implmented')
        self.process_dict.update(proj_dict)
    def addResizeOption(self, extent):
        """ Add resize parameters to espa order dictionary dictionary
            
        Args:
            extent (dict) dict with keys xmin, xmax, ymin, ymax
        """
        extent_dict = {"image_extents": {
                            "north": extent['ymax'],
                            "south": extent['ymin'],
                            "east": extent['xmax'],
                            "west": extent['xmin'],
                            "units": "dd"
                        }}
        self.process_dict.update(extent_dict)
    def getDict(self):
        """ Retrieve dictionary generated
        """
        return self.process_dict
        