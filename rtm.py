#%% (1) Grab and process the data

from obspy import UTCDateTime
import json
from waveform_utils import gather_waveforms, gather_waveforms_bulk,\
                           process_waveforms


# Start and end of time window containing (suspected) events
STARTTIME = UTCDateTime('2019-06-20T23:55:00')
ENDTIME = STARTTIME + 60*60

REMOVE_RESPONSE = True  # Toggle removing sensitivity or not

FREQ_MIN = 0.5          # [Hz] Lower bandpass corner
FREQ_MAX = 2            # [Hz] Upper bandpass corner

DECIMATION_RATE = 0.05  # [Hz] New sampling rate to use for decimation

SMOOTH_WIN = 120        # [s] Smoothing window duration

AGC_WIN = 250           # [s] AGC window duration
AGC_METHOD = 'gismo'    # Method to use for AGC, specify 'gismo' or 'walker'

LON_0 = -153.0918       # [deg] Longitude of grid center
LAT_0 = 60.0319         # [deg] Latitude of grid center

BULK = True             # Toggle using bulk station search or not

MAX_RADIUS = 650        # [km] Radius within which to search for stations


# watc_credentials.json contains a single line with format ["user", "password"]
with open('watc_credentials.json') as f:
    watc_username, watc_password = json.load(f)

if BULK:
    st = gather_waveforms_bulk(LON_0, LAT_0, MAX_RADIUS, STARTTIME, ENDTIME,
                               remove_response=REMOVE_RESPONSE,
                               watc_username=watc_username,
                               watc_password=watc_password)
else:
    st = gather_waveforms(source='IRIS', network='AV,AK,IM,TA',
                          station='HOM,M22K,O20K,RC01,DLL,I53H?',
                          starttime=STARTTIME, endtime=ENDTIME,
                          remove_response=REMOVE_RESPONSE,
                          watc_username=watc_username,
                          watc_password=watc_password)

agc_params = dict(win_sec=AGC_WIN, method=AGC_METHOD)

st_proc = process_waveforms(st=st, freqmin=FREQ_MIN, freqmax=FREQ_MAX,
                            envelope=True, smooth_win=SMOOTH_WIN,
                            decimation_rate=DECIMATION_RATE, agc_params=None,
                            normalize=True, plot_steps=False)

#%% (2) Define grid and perform grid search

from grid_utils import define_grid, grid_search

PROJECTED = False

if PROJECTED:
    X_RADIUS = 50000  # [m] E-W grid radius (half of grid "width")
    Y_RADIUS = 50000  # [m] N-S grid radius (half of grid "height")
    SPACING = 5000    # [m] Grid spacing

else:
    X_RADIUS = 2   # [deg] E-W grid radius (half of grid "width")
    Y_RADIUS = 2   # [deg] N-S grid radius (half of grid "height")
    SPACING = 0.1  # [deg] Grid spacing

STACK_METHOD = 'sum'  # Choose either 'sum' or 'product'

CELERITY_LIST = [295, 300, 305]  # [m/s]

grid = define_grid(lon_0=LON_0, lat_0=LAT_0, x_radius=X_RADIUS,
                   y_radius=Y_RADIUS, spacing=SPACING, projected=PROJECTED,
                   plot_preview=False)

S, shifted_streams = grid_search(processed_st=st_proc, grid=grid,
                                 celerity_list=CELERITY_LIST,
                                 stack_method=STACK_METHOD)

#%% (3) Plot

from plotting_utils import plot_time_slice, plot_record_section
from obspy import UTCDateTime
import utm

fig = plot_time_slice(S, st_proc, time_slice=None, celerity_slice=None,
                      label_stations=False, hires=False)

max_coords = S.where(S == S.max(), drop=True)[0, 0, 0, 0].coords

max_x = max_coords['x'].values
max_y = max_coords['y'].values
max_time = max_coords['time'].values
max_celerity = max_coords['celerity'].values

# Projected case
if S.attrs['UTM']:
    max_loc = utm.to_latlon(max_x, max_y, zone_number=S.attrs['UTM']['zone'],
                            northern=not S.attrs['UTM']['southern_hemisphere'])
# Unprojected case
else:
    max_loc = max_y, max_x

fig = plot_record_section(st_proc, UTCDateTime(str(max_time)), max_loc,
                          plot_celerity='range', label_waveforms=False)

#%% DEM sandbox

from grid_utils import define_grid
from osgeo import gdal, osr
import matplotlib.pyplot as plt
import numpy as np
import cartopy.crs as ccrs

gdal.UseExceptions()

SPACING = 5

# Yasur
grid = define_grid(lon_0=169.447, lat_0=-19.532, x_radius=7000,
                   y_radius=7000, spacing=SPACING, projected=True,
                   plot_preview=False)

input_raster = 'DEM_Union_UAV_161116_sm101.tif'
output_raster = 'out.tif'

dest_srs = osr.SpatialReference()
proj_string = '+proj=utm +zone={} +datum=WGS84'.format(grid.attrs['UTM']['zone'])
if grid.attrs['UTM']['southern_hemisphere']:
    proj_string += ' +south'
dest_srs.ImportFromProj4(proj_string)

ds = gdal.Warp(output_raster, input_raster, dstSRS=dest_srs,
               outputBounds=(grid.x.min() - SPACING/2,
                             grid.y.min() - SPACING/2,
                             grid.x.max() + SPACING/2,
                             grid.y.max() + SPACING/2),
               xRes=SPACING, yRes=SPACING, resampleAlg='lanczos'
               )

dem = np.flipud(ds.GetRasterBand(1).ReadAsArray())

dem[dem == dem.min()] = np.nan

ds = None

proj = ccrs.UTM(**grid.attrs['UTM'])

fig, ax = plt.subplots(figsize=(10, 10),
                       subplot_kw=dict(projection=proj))


def hill_shade(elev, altitude=45, azimuth=45):
    altitude = np.deg2rad(altitude)
    azimuth = np.deg2rad(azimuth)
    x, y = np.gradient(elev)
    slope = np.pi/2. - np.arctan(np.sqrt(x**2 + y**2))
    aspect = np.arctan2(-x, y)

    shaded = (np.sin(altitude) * np.sin(slope) +
              np.cos(altitude) * np.cos(slope) *
              np.cos((azimuth - np.pi/2.) - aspect))
    return shaded


shaded = hill_shade(dem, altitude=40, azimuth=45)

grid_dem = grid.copy()
grid_dem.data = dem
grid_dem.plot.imshow(ax=ax, transform=proj, add_colorbar=False, cmap='viridis',
                     zorder=5)

grid_shaded = grid.copy()
grid_shaded.data = shaded
grid_shaded.plot.imshow(ax=ax, transform=proj, alpha=0.5,
                        cmap='Greys_r', add_colorbar=False, zorder=10)

# Plot the center of the grid
ax.scatter(*grid.attrs['grid_center'], color='red', transform=ccrs.Geodetic(),
           zorder=20)

fig.canvas.draw()
fig.tight_layout()
fig.show()
