  
import ee
ee.Authenticate()
ee.Initialize(project='ee-xbosonai')
print(ee.Image("NASA/NASADEM_HGT/001").get("title").getInfo())
import folium
from datetime import datetime
from ee.batch import Export

def toDB(img):
    if isinstance(img, ee.Image):
        return ee.Image(img).log10().multiply(10.0)
    else:
        raise ValueError("Input is not an Earth Engine image")

# Define the toNatural function
def toNatural(img):
    return ee.Image(10.0).pow(img.select(0).divide(10.0))
# Define the RefinedLee function
def RefinedLee(img):
    # Implementation of Refined Lee Speckle filter here
    # This function should return the filtered image
    return result
# Load Global Surface Water (GSW) dataset
gsw = ee.Image('JRC/GSW1_1/GlobalSurfaceWater').select('seasonality')

# Load HydroSHEDS dataset
hydrosheds = ee.Image('WWF/HydroSHEDS/03VFDEM')



# Define date ranges
beforeStart = '2018-07-15'
beforeEnd = '2018-08-10'
afterStart = '2018-08-10'
afterEnd = '2018-08-23'

# Load administrative boundary dataset from Earth Engine
admin2 = ee.FeatureCollection('FAO/GAUL_SIMPLIFIED_500m/2015/level2')

# Filter the administrative boundary for Ernakulam district
ernakulam = admin2.filter(ee.Filter.eq('ADM2_NAME', 'Ernakulam'))
geometry = ernakulam.geometry()

# Create a folium Map object
my_map = folium.Map(location=[0, 0], zoom_start=2)


# Load Sentinel-1 GRD data
collection = ee.ImageCollection('COPERNICUS/S1_GRD') \
    .filter(ee.Filter.eq('instrumentMode', 'IW')) \
    .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH')) \
    .filter(ee.Filter.eq('orbitProperties_pass', 'DESCENDING')) \
    .filter(ee.Filter.eq('resolution_meters', 10)) \
    .filterBounds(geometry) \
    .select('VH')
# Filter collections for before and after flood dates
beforeCollection = collection.filterDate(beforeStart, beforeEnd)
afterCollection = collection.filterDate(afterStart, afterEnd)

# Create mosaics for before and after flood dates
before = beforeCollection.mosaic().clip(geometry)
after = afterCollection.mosaic().clip(geometry)


# Add the boundary to the map
folium.GeoJson(geometry.getInfo(), name='Ernakulam District').add_to(my_map)

# Add layers to the map
folium.TileLayer(
    tiles=before.getMapId({'min': -25, 'max': 0})['tile_fetcher'].url_format,
    attr='Before Floods',
    overlay=True,
).add_to(my_map)
folium.TileLayer(
    tiles=after.getMapId({'min': -25, 'max': 0})['tile_fetcher'].url_format,
    attr='After Floods',
    overlay=True,
).add_to(my_map)




# Apply speckle filtering
beforeFiltered = toDB(RefinedLee(toNatural(before)))
afterFiltered = toDB(RefinedLee(toNatural(after)))
# Implement the toDB and RefinedLee functions

# Calculate the difference
difference = afterFiltered.divide(beforeFiltered)

# Define a threshold
diffThreshold = 1.25

# Initial estimate of flooded pixels
flooded = difference.gt(diffThreshold).rename('water').selfMask()
folium.TileLayer(
    tiles=flooded.getMapId({'min': 0, 'max': 1, 'palette': ['orange']}),
    attr='Initial Flood Area',
    overlay=True,
).add_to(my_map)

# Mask out areas with permanent water
permanentWater = gsw.select('seasonality').gte(5).clip(geometry)
flooded = flooded.where(permanentWater, 0).selfMask()
folium.Map.addLayer(permanentWater.selfMask(), {'min': 0, 'max': 1, 'palette': ['blue']}, 'Permanent Water')

# Mask out areas with more than 5 percent slope using the HydroSHEDS DEM
slopeThreshold = 5
terrain = ee.Algorithms.Terrain(hydrosheds)
slope = terrain.select('slope')
flooded = flooded.updateMask(slope.lt(slopeThreshold))
folium.Map.addLayer(slope.gte(slopeThreshold).selfMask(), {'min': 0, 'max': 1, 'palette': ['cyan']}, 'Steep Areas', False)

# Remove isolated pixels
connectedPixelThreshold = 8
connections = flooded.connectedPixelCount(25)
flooded = flooded.updateMask(connections.gt(connectedPixelThreshold))
folium.Map.addLayer(connections.lte(connectedPixelThreshold).selfMask(), {'min': 0, 'max': 1, 'palette': ['yellow']}, 'Disconnected Areas', False)

folium.Map.addLayer(flooded, {'min': 0, 'max': 1, 'palette': ['red']}, 'Flooded Areas')

# Calculate affected area
print('Total District Area (Ha)', geometry.area().divide(10000))

stats = flooded.multiply(ee.Image.pixelArea()).reduceRegion({
    'reducer': ee.Reducer.sum(),
    'geometry': geometry,
    'scale': 30,
    'maxPixels': 1e10,
    'tileScale': 16
})
print('Flooded Area (Ha)', ee.Number(stats.get('water')).divide(10000))

# Export flooded area data to Drive
flooded_area = ee.Number(stats.get('water')).divide(10000)
feature = ee.Feature(None, {'flooded_area': flooded_area})
fc = ee.FeatureCollection([feature])

task = ee.batch.Export.table.toDrive({
    'collection': fc,
    'description': 'Flooded_Area_Export',
    'folder': 'earthengine',
    'fileNamePrefix': 'flooded_area',
    'fileFormat': 'CSV'
})
task.start()





