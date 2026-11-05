#!/usr/bin/env python3
"""
Generate a map of England library authorities showing which charge fees to reserve books.

This script creates a choropleth map visualizing library reservation fees
across English library authorities based on data from library_reservation_fees.csv.

Usage:
    python generate_map.py [--interactive] [--output FILE] [--summary]

Options:
    --interactive    Generate an interactive HTML map (uses folium)
    --output FILE    Save the map to FILE (default: output/uk_library_fees_map.png for static, output/uk_library_fees_map.html for interactive)
    --dpi DPI        DPI for static map (default: 300)
    --csv CSV        Path to CSV file (default: library_reservation_fees.csv)
    --summary        Print data summary only

Note: Static map output generates both PNG and SVG files.
"""

import argparse
import sys
import os
import warnings
warnings.filterwarnings('ignore')

try:
    import pandas as pd
    import geopandas as gpd
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    from matplotlib.patches import Patch
    import folium
    from branca.element import MacroElement, Template
    HAS_DEPENDENCIES = True
except ImportError as e:
    HAS_DEPENDENCIES = False
    print(f"Missing required package: {e}")
    print("\nPlease install: pip install pandas geopandas matplotlib folium shapely")
    sys.exit(1)


# Mapping of Local Authority Districts (LAD13) to their governing Library Authority in England.
# Unitary authorities, London boroughs, and Metropolitan boroughs are 1:1.
# Non-metropolitan districts are mapped to their respective County Council.
# Historic/reorganized districts (pre-2019/2021/2023) are mapped to their current successor authorities.
DISTRICT_TO_AUTHORITY = {
    # Direct Unitary aliases in LAD13
    'Kingston upon Hull, City of': 'Kingston upon Hull',
    'Herefordshire, County of': 'Herefordshire',
    'Bristol, City of': 'Bristol',
    'County Durham': 'Durham',
    'St. Helens': 'St Helens',

    # Dorset (pre-2019 reorganization in LAD13)
    'Bournemouth': 'Bournemouth, Christchurch and Poole',
    'Christchurch': 'Bournemouth, Christchurch and Poole',
    'Poole': 'Bournemouth, Christchurch and Poole',
    'East Dorset': 'Dorset',
    'North Dorset': 'Dorset',
    'Purbeck': 'Dorset',
    'West Dorset': 'Dorset',
    'Weymouth and Portland': 'Dorset',

    # Northamptonshire (pre-2021 reorganization in LAD13)
    'Corby': 'North Northamptonshire',
    'East Northamptonshire': 'North Northamptonshire',
    'Kettering': 'North Northamptonshire',
    'Wellingborough': 'North Northamptonshire',
    'Daventry': 'West Northamptonshire',
    'Northampton': 'West Northamptonshire',
    'South Northamptonshire': 'West Northamptonshire',

    # Cumbria (pre-2023 reorganization in LAD13)
    'Allerdale': 'Cumberland',
    'Carlisle': 'Cumberland',
    'Copeland': 'Cumberland',
    'Barrow-in-Furness': 'Westmorland and Furness',
    'Eden': 'Westmorland and Furness',
    'South Lakeland': 'Westmorland and Furness',

    # Buckinghamshire (pre-2020 reorganization in LAD13)
    'Aylesbury Vale': 'Buckinghamshire',
    'Chiltern': 'Buckinghamshire',
    'South Bucks': 'Buckinghamshire',
    'Wycombe': 'Buckinghamshire',

    # Somerset (pre-2019/2023 reorganization in LAD13)
    'Mendip': 'Somerset',
    'Sedgemoor': 'Somerset',
    'South Somerset': 'Somerset',
    'Taunton Deane': 'Somerset',
    'West Somerset': 'Somerset',

    # North Yorkshire (pre-2023 reorganization in LAD13)
    'Craven': 'North Yorkshire',
    'Hambleton': 'North Yorkshire',
    'Harrogate': 'North Yorkshire',
    'Richmondshire': 'North Yorkshire',
    'Ryedale': 'North Yorkshire',
    'Scarborough': 'North Yorkshire',
    'Selby': 'North Yorkshire',

    # Cambridgeshire County Council districts
    'Cambridge': 'Cambridgeshire',
    'East Cambridgeshire': 'Cambridgeshire',
    'Fenland': 'Cambridgeshire',
    'Huntingdonshire': 'Cambridgeshire',
    'South Cambridgeshire': 'Cambridgeshire',

    # Derbyshire County Council districts
    'Amber Valley': 'Derbyshire',
    'Bolsover': 'Derbyshire',
    'Chesterfield': 'Derbyshire',
    'Derbyshire Dales': 'Derbyshire',
    'Erewash': 'Derbyshire',
    'High Peak': 'Derbyshire',
    'North East Derbyshire': 'Derbyshire',
    'South Derbyshire': 'Derbyshire',

    # Devon County Council districts
    'East Devon': 'Devon',
    'Exeter': 'Devon',
    'Mid Devon': 'Devon',
    'North Devon': 'Devon',
    'South Hams': 'Devon',
    'Teignbridge': 'Devon',
    'Torridge': 'Devon',
    'West Devon': 'Devon',

    # East Sussex County Council districts
    'Eastbourne': 'East Sussex',
    'Hastings': 'East Sussex',
    'Lewes': 'East Sussex',
    'Rother': 'East Sussex',
    'Wealden': 'East Sussex',

    # Essex County Council districts
    'Basildon': 'Essex',
    'Braintree': 'Essex',
    'Brentwood': 'Essex',
    'Castle Point': 'Essex',
    'Chelmsford': 'Essex',
    'Colchester': 'Essex',
    'Epping Forest': 'Essex',
    'Harlow': 'Essex',
    'Maldon': 'Essex',
    'Rochford': 'Essex',
    'Tendring': 'Essex',
    'Uttlesford': 'Essex',

    # Gloucestershire County Council districts
    'Cheltenham': 'Gloucestershire',
    'Cotswold': 'Gloucestershire',
    'Forest of Dean': 'Gloucestershire',
    'Gloucester': 'Gloucestershire',
    'Stroud': 'Gloucestershire',
    'Tewkesbury': 'Gloucestershire',

    # Hampshire County Council districts
    'Basingstoke and Deane': 'Hampshire',
    'East Hampshire': 'Hampshire',
    'Eastleigh': 'Hampshire',
    'Fareham': 'Hampshire',
    'Gosport': 'Hampshire',
    'Hart': 'Hampshire',
    'Havant': 'Hampshire',
    'New Forest': 'Hampshire',
    'Rushmoor': 'Hampshire',
    'Test Valley': 'Hampshire',
    'Winchester': 'Hampshire',

    # Hertfordshire County Council districts
    'Broxbourne': 'Hertfordshire',
    'Dacorum': 'Hertfordshire',
    'East Hertfordshire': 'Hertfordshire',
    'Hertsmere': 'Hertfordshire',
    'North Hertfordshire': 'Hertfordshire',
    'St Albans': 'Hertfordshire',
    'Stevenage': 'Hertfordshire',
    'Three Rivers': 'Hertfordshire',
    'Watford': 'Hertfordshire',
    'Welwyn Hatfield': 'Hertfordshire',

    # Kent County Council districts
    'Ashford': 'Kent',
    'Canterbury': 'Kent',
    'Dartford': 'Kent',
    'Dover': 'Kent',
    'Gravesham': 'Kent',
    'Maidstone': 'Kent',
    'Sevenoaks': 'Kent',
    'Shepway': 'Kent',
    'Swale': 'Kent',
    'Thanet': 'Kent',
    'Tonbridge and Malling': 'Kent',
    'Tunbridge Wells': 'Kent',

    # Lancashire County Council districts
    'Burnley': 'Lancashire',
    'Chorley': 'Lancashire',
    'Fylde': 'Lancashire',
    'Hyndburn': 'Lancashire',
    'Lancaster': 'Lancashire',
    'Pendle': 'Lancashire',
    'Preston': 'Lancashire',
    'Ribble Valley': 'Lancashire',
    'Rossendale': 'Lancashire',
    'South Ribble': 'Lancashire',
    'West Lancashire': 'Lancashire',
    'Wyre': 'Lancashire',

    # Leicestershire County Council districts
    'Blaby': 'Leicestershire',
    'Charnwood': 'Leicestershire',
    'Harborough': 'Leicestershire',
    'Hinckley and Bosworth': 'Leicestershire',
    'Melton': 'Leicestershire',
    'North West Leicestershire': 'Leicestershire',
    'Oadby and Wigston': 'Leicestershire',

    # Lincolnshire County Council districts
    'Boston': 'Lincolnshire',
    'East Lindsey': 'Lincolnshire',
    'Lincoln': 'Lincolnshire',
    'North Kesteven': 'Lincolnshire',
    'South Holland': 'Lincolnshire',
    'South Kesteven': 'Lincolnshire',
    'West Lindsey': 'Lincolnshire',

    # Norfolk County Council districts
    'Breckland': 'Norfolk',
    'Broadland': 'Norfolk',
    'Great Yarmouth': 'Norfolk',
    "King's Lynn and West Norfolk": 'Norfolk',
    'North Norfolk': 'Norfolk',
    'Norwich': 'Norfolk',
    'South Norfolk': 'Norfolk',

    # Nottinghamshire County Council districts
    'Ashfield': 'Nottinghamshire',
    'Bassetlaw': 'Nottinghamshire',
    'Broxtowe': 'Nottinghamshire',
    'Gedling': 'Nottinghamshire',
    'Mansfield': 'Nottinghamshire',
    'Newark and Sherwood': 'Nottinghamshire',
    'Rushcliffe': 'Nottinghamshire',

    # Oxfordshire County Council districts
    'Cherwell': 'Oxfordshire',
    'Oxford': 'Oxfordshire',
    'South Oxfordshire': 'Oxfordshire',
    'Vale of White Horse': 'Oxfordshire',
    'West Oxfordshire': 'Oxfordshire',

    # Staffordshire County Council districts
    'Cannock Chase': 'Staffordshire',
    'East Staffordshire': 'Staffordshire',
    'Lichfield': 'Staffordshire',
    'Newcastle-under-Lyme': 'Staffordshire',
    'South Staffordshire': 'Staffordshire',
    'Stafford': 'Staffordshire',
    'Staffordshire Moorlands': 'Staffordshire',
    'Tamworth': 'Staffordshire',

    # Suffolk County Council districts
    'Babergh': 'Suffolk',
    'Forest Heath': 'Suffolk',
    'Ipswich': 'Suffolk',
    'Mid Suffolk': 'Suffolk',
    'St Edmundsbury': 'Suffolk',
    'Suffolk Coastal': 'Suffolk',
    'Waveney': 'Suffolk',

    # Surrey County Council districts
    'Elmbridge': 'Surrey',
    'Epsom and Ewell': 'Surrey',
    'Guildford': 'Surrey',
    'Mole Valley': 'Surrey',
    'Reigate and Banstead': 'Surrey',
    'Runnymede': 'Surrey',
    'Spelthorne': 'Surrey',
    'Surrey Heath': 'Surrey',
    'Tandridge': 'Surrey',
    'Waverley': 'Surrey',
    'Woking': 'Surrey',

    # Warwickshire County Council districts
    'North Warwickshire': 'Warwickshire',
    'Nuneaton and Bedworth': 'Warwickshire',
    'Rugby': 'Warwickshire',
    'Stratford-on-Avon': 'Warwickshire',
    'Warwick': 'Warwickshire',

    # West Sussex County Council districts
    'Adur': 'West Sussex',
    'Arun': 'West Sussex',
    'Chichester': 'West Sussex',
    'Crawley': 'West Sussex',
    'Horsham': 'West Sussex',
    'Mid Sussex': 'West Sussex',
    'Worthing': 'West Sussex',

    # Worcestershire County Council districts
    'Bromsgrove': 'Worcestershire',
    'Malvern Hills': 'Worcestershire',
    'Redditch': 'Worcestershire',
    'Worcester': 'Worcestershire',
    'Wychavon': 'Worcestershire',
    'Wyre Forest': 'Worcestershire',
}


def load_data(csv_path='library_reservation_fees.csv'):
    """Load the reservation fees data from CSV."""
    try:
        df = pd.read_csv(csv_path)
        # Filter for England
        df = df[df['country'] == 'England'].copy()
        print(f"Loaded {len(df)} England records from {csv_path}")
        return df
    except FileNotFoundError:
        print(f"Error: CSV file not found at {csv_path}")
        sys.exit(1)


def load_geojson():
    """Load England local authority boundaries GeoJSON."""
    local_files = ['england_lad.geojson', 'uk_counties.geojson']
    for loc in local_files:
        if os.path.exists(loc):
            gdf = gpd.read_file(loc)
            if 'LAD13CD' in gdf.columns:
                gdf = gdf[gdf['LAD13CD'].str.startswith('E')].copy()
            print(f"Loaded local GeoJSON: {loc} ({len(gdf)} features)")
            return gdf

    url = 'https://github.com/martinjc/UK-GeoJSON/raw/master/json/administrative/gb/lad.json'
    try:
        print(f"Downloading boundaries from {url}...")
        gdf = gpd.read_file(url)
        # Filter to England (district code prefix 'E')
        gdf = gdf[gdf['LAD13CD'].str.startswith('E')].copy()
        # Save local cache
        gdf.to_file('england_lad.geojson', driver='GeoJSON')
        print(f"Loaded and cached {len(gdf)} England features")
        return gdf
    except Exception as e:
        print(f"Error downloading GeoJSON: {e}")
        sys.exit(1)


def match_data(df, gdf):
    """Match CSV library authority data to England GeoJSON features."""
    name_col = None
    for col in gdf.columns:
        if 'LAD13NM' in col or 'NAME' in col or 'name' in col.lower():
            name_col = col
            break

    if name_col is None:
        print("Could not find name column in GeoJSON")
        sys.exit(1)

    print(f"Using GeoJSON name column: {name_col}")

    # Build authority lookup from CSV
    auth_lookup = {}
    for _, row in df.iterrows():
        auth_lookup[row['county']] = row.to_dict()

    result_gdf = gdf.copy()

    # Initialize columns
    for col in ['authority', 'charge_fee', 'amount', 'amount_notes', 'source', 'source_url', 'notes', 'region']:
        result_gdf[col] = 'Unknown'

    matched_count = 0
    for idx, row in result_gdf.iterrows():
        district_name = str(row[name_col]).strip()
        auth_name = DISTRICT_TO_AUTHORITY.get(district_name, district_name)

        if auth_name in auth_lookup:
            info = auth_lookup[auth_name]
            result_gdf.at[idx, 'authority'] = auth_name
            result_gdf.at[idx, 'charge_fee'] = info.get('charge_fee', 'Unknown')
            result_gdf.at[idx, 'amount'] = info.get('amount', '£0.00')
            result_gdf.at[idx, 'amount_notes'] = info.get('amount_notes', '')
            result_gdf.at[idx, 'source'] = info.get('source', '')
            result_gdf.at[idx, 'source_url'] = info.get('source_url', '')
            result_gdf.at[idx, 'notes'] = info.get('notes', '')
            result_gdf.at[idx, 'region'] = info.get('region', '')
            matched_count += 1
        else:
            print(f"Warning: unmatched district {district_name} (mapped as: {auth_name})")

    print(f"Successfully matched {matched_count} of {len(result_gdf)} districts to library authorities.")
    return result_gdf


def create_static_map(merged_gdf, output_file='output/uk_library_fees_map.png', dpi=300):
    """Create a static choropleth map using matplotlib with colorblind-friendly palette.
    
    Saves both PNG and SVG versions of the map.
    """
    fig, ax = plt.subplots(1, 1, figsize=(16, 20), facecolor='#f8f9fa')
    ax.set_facecolor('#f8f9fa')

    # Colorblind-safe palette (Okabe-Ito universal standard: Blue for Free, Vermilion/Orange for Fee)
    colors = {
        'No': '#0072B2',       # Blue: Free
        'Yes': '#D55E00',      # Vermilion / Amber-Orange: Charges Fee
        'Unknown': '#CCCCCC'   # Light Grey: Unknown
    }

    # Assign explicit color column to prevent colormap normalization index bugs
    merged_gdf['plot_color'] = merged_gdf['charge_fee'].map(colors).fillna(colors['Unknown'])

    merged_gdf.plot(
        color=merged_gdf['plot_color'],
        ax=ax,
        edgecolor='#ffffff',
        linewidth=0.5,
    )

    # Calculate authority counts for legend
    auth_counts = merged_gdf.drop_duplicates(subset=['authority'])['charge_fee'].value_counts()
    no_count = auth_counts.get('No', 0)
    yes_count = auth_counts.get('Yes', 0)

    legend_elements = [
        Patch(facecolor=colors['No'], edgecolor='#004b75', label=f'Free ({no_count} authorities)'),
        Patch(facecolor=colors['Yes'], edgecolor='#993d00', label=f'Charges Fee ({yes_count} authorities)'),
    ]
    ax.legend(
        handles=legend_elements,
        loc='lower right',
        fontsize=13,
        title='Online Book Reservation Fee',
        title_fontsize=14,
        frameon=True,
        facecolor='#ffffff',
        edgecolor='#cccccc',
        framealpha=0.95
    )

    ax.set_title(
        'England Library Reservation Fees\nOnline Book Holds by Local Authority',
        fontsize=20,
        fontweight='bold',
        pad=20,
        color='#1a1a1a'
    )
    ax.axis('off')

    plt.tight_layout()
    
    # Save PNG
    plt.savefig(output_file, dpi=dpi, bbox_inches='tight')
    print(f"Map saved to {output_file}")
    
    # Save SVG
    svg_output_file = os.path.splitext(output_file)[0] + '.svg'
    plt.savefig(svg_output_file, format='svg', bbox_inches='tight')
    print(f"SVG map saved to {svg_output_file}")
    
    plt.close()


class LeafletLegendControl(MacroElement):
    """Native Leaflet legend control rendered directly inside the map container."""
    def __init__(self, title, items, position='bottomright'):
        super().__init__()
        self._template = Template('''
            {% macro script(this, kwargs) %}
            var legend = L.control({position: '{{ this.position }}'});
            legend.onAdd = function (map) {
                var div = L.DomUtil.create('div', 'info legend');
                div.style.backgroundColor = 'rgba(255, 255, 255, 0.95)';
                div.style.padding = '12px 16px';
                div.style.border = '2px solid #bbb';
                div.style.borderRadius = '6px';
                div.style.boxShadow = '0 2px 8px rgba(0,0,0,0.25)';
                div.style.fontFamily = 'Arial, sans-serif';
                div.style.fontSize = '13px';
                div.style.lineHeight = '22px';
                div.style.pointerEvents = 'auto';

                div.innerHTML = '<div style="font-weight: bold; font-size: 14px; margin-bottom: 6px; color: #111;">{{ this.title }}</div>' +
                    '{% for color, label in this.items %}' +
                    '<div style="margin-bottom: 4px; display: flex; align-items: center;">' +
                    '<span style="background: {{ color }}; width: 16px; height: 16px; display: inline-block; border-radius: 3px; margin-right: 8px; border: 1px solid rgba(0,0,0,0.25); flex-shrink: 0;"></span>' +
                    '<span style="color: #222;">{{ label }}</span>' +
                    '</div>' +
                    '{% endfor %}';
                return div;
            };
            legend.addTo({{ this._parent.get_name() }});
            {% endmacro %}
        ''')
        self.title = title
        self.items = items
        self.position = position


def create_interactive_map(merged_gdf, output_file='output/uk_library_fees_map.html'):
    """Create an interactive map using folium with key-free basemaps and colorblind-friendly palette."""
    minx, miny, maxx, maxy = merged_gdf.total_bounds

    # OpenStreetMap requires no API key
    m = folium.Map(
        location=[(miny + maxy) / 2, (minx + maxx) / 2],
        zoom_start=7,
        tiles='OpenStreetMap',
        name='OpenStreetMap'
    )

    # Add Esri Light Gray Canvas as a subtle neutral alternative (no API key required)
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}',
        attr='Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ',
        name='Light Gray (Esri)'
    ).add_to(m)

    # Colorblind-safe palette (Okabe-Ito)
    color_map = {
        'No': '#0072B2',       # Blue: Free
        'Yes': '#D55E00',      # Vermilion / Amber-Orange: Charges Fee
        'Unknown': '#CCCCCC'
    }

    # Count authorities
    auth_counts = merged_gdf.drop_duplicates(subset=['authority'])['charge_fee'].value_counts()
    no_count = auth_counts.get('No', 0)
    yes_count = auth_counts.get('Yes', 0)

    for idx, row in merged_gdf.iterrows():
        if row['geometry'] is not None:
            try:
                style = {
                    'fillColor': color_map.get(row['charge_fee'], '#CCCCCC'),
                    'color': '#ffffff',
                    'weight': 0.8,
                    'fillOpacity': 0.75
                }

                tooltip_text = (
                    f"<b>District:</b> {row['LAD13NM']}<br>"
                    f"<b>Library Authority:</b> {row['authority']}<br>"
                    f"<b>Charges Fee:</b> {row['charge_fee']}<br>"
                    f"<b>Amount:</b> {row['amount']}<br>"
                    f"<b>Details:</b> {row['amount_notes']}<br>"
                    f"<b>Notes:</b> {row['notes']}<br>"
                    f"<b>Source:</b> {row['source']}"
                )

                folium.GeoJson(
                    row['geometry'].__geo_interface__,
                    style_function=lambda x, s=style: s,
                    tooltip=folium.Tooltip(tooltip_text)
                ).add_to(m)
            except Exception:
                continue

    # Add native Leaflet Legend Control to map
    legend_items = [
        ('#0072B2', f'Free ({no_count} authorities)'),
        ('#D55E00', f'Charges Fee ({yes_count} authorities)'),
    ]
    legend_ctrl = LeafletLegendControl(
        title='Online Reservation Fee',
        items=legend_items,
        position='bottomright'
    )
    m.add_child(legend_ctrl)

    folium.LayerControl().add_to(m)

    m.save(output_file)
    print(f"Interactive map saved to {output_file}")


def print_summary(df):
    """Print a data summary for England."""
    print("\n" + "="*60)
    print("ENGLAND LIBRARY RESERVATION FEES DATA SUMMARY")
    print("="*60)

    total = len(df)
    yes = len(df[df['charge_fee'] == 'Yes'])
    no = len(df[df['charge_fee'] == 'No'])
    unknown = total - yes - no

    print(f"Total English Library Authorities: {total}")
    print(f"  No fees (Free): {no} ({no/total*100:.1f}%)")
    print(f"  Charges fee:   {yes} ({yes/total*100:.1f}%)")
    if unknown > 0:
        print(f"  Unknown:       {unknown} ({unknown/total*100:.1f}%)")

    print("\nBreakdown by Region:")
    for region, group in df.groupby('region'):
        r_yes = (group['charge_fee'] == 'Yes').sum()
        r_no = (group['charge_fee'] == 'No').sum()
        print(f"  {region:25s}: {len(group):2d} authorities (Free: {r_no:2d}, Fee: {r_yes:2d})")
    print("="*60)


def main():
    parser = argparse.ArgumentParser(description='Generate England library fees map')
    parser.add_argument('--interactive', action='store_true', help='Generate interactive HTML map')
    parser.add_argument('--output', type=str, default=None)
    parser.add_argument('--dpi', type=int, default=300)
    parser.add_argument('--csv', type=str, default='library_reservation_fees.csv')
    parser.add_argument('--summary', action='store_true', help='Print summary statistics only')

    args = parser.parse_args()

    df = load_data(args.csv)

    if args.summary:
        print_summary(df)
        return

    print("\nLoading England boundaries...")
    gdf = load_geojson()

    print("\nMatching data...")
    merged_gdf = match_data(df, gdf)

    # Ensure output directory exists
    os.makedirs('output', exist_ok=True)

    if args.interactive:
        if args.output:
            output_file = os.path.join('output', args.output)
        else:
            output_file = 'output/uk_library_fees_map.html'
        create_interactive_map(merged_gdf, output_file)
    else:
        if args.output:
            output_file = os.path.join('output', args.output)
        else:
            output_file = 'output/uk_library_fees_map.png'
        create_static_map(merged_gdf, output_file, args.dpi)

    print_summary(df)
    print("\nDone!")


if __name__ == '__main__':
    main()
