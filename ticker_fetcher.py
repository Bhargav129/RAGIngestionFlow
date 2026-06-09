from pathlib import Path

import requests
import os
import json
import datetime

from src.repositories.file_operation_repo import FileOperationRepo


symbols_url = "https://public.fyers.in/sym_details/NSE_CM_sym_master.json"

response = requests.get(symbols_url)

file_data = []

file_name = Path("./symbols.json")

file_repo = FileOperationRepo(file_name)



if os.path.exists(file_name):
    try:
       file_data = file_repo.file_reader("r")
    except Exception as e:
        print(e)
else:
    os.system("touch {}".format(file_name))



if response.status_code == 200:
    resp = response.json()



    """
    Sample json data
    
    {'fyToken': '101000000016921', 'exToken': 16921, 'exSymbol': '20MICRONS', 'exSymName': '20 MICRONS LTD',
     'exchange': 10, 'segment': 10, 'exSeries': 'EQ', 'exInstType': 0, 'tradeStatus': 1, 'underSym': '20MICRONS',
     'underFyTok': '101000000016921', 'expiryDate': '', 'optType': 'XX', 'strikePrice': -1.0, 'minLotSize': 1,
     'tickSize': 0.01, 'isin': 'INE144J01027', 'symDetails': '20 MICRONS LTD', 'upperPrice': 194.84,
     'lowerPrice': 129.9, 'faceValue': 5.0, 'qtyFreeze': '615855', 'lastUpdate': '2026-04-10',
     'tradingSession': '0915-1530|1815-1915:', 'currencyCode': 'INR', 'symTicker': 'NSE:20MICRONS-EQ',
     'exchangeName': 'NSE', 'symbolDesc': '20 MICRONS LTD', 'qtyMultiplier': 1.0, 'originalExpDate': None,
     'previousOi': 0.0, 'previousClose': 162.37, 'is_mtf_tradable': 0, 'mtf_margin': 0.0, 'asmGsmVal': '', 'stream': '',
     'cautionary_msg': '', 'symbolDetails': '20 MICRONS LTD', 'mpp_flag': 0, 'allow_pre_open': 1,
     'display_format_mob': '20 Microns Ltd.', 'short_name': '20MICRONS-EQ', 'has_options': False, 'has_futures': False}
     
     
     """

    current_year = datetime.datetime.now().year

    BUFFER_YEARS = 5

    years_status = {current_year-i:"pending"  for i in range(BUFFER_YEARS)}


    api_data = [{"ticker_name":val.get("exSymName"), "ticker_symbol":val.get("exSymbol"), "isin":val.get("isin"),
                     "status":years_status}
                    for key, val in resp.items() if val.get('exSeries') == 'EQ' and val.get('isin').startswith('INE')]


    if not file_data:
        file_repo.file_writer("w", api_data)
    else:
        existing_isins = [item.get("isin") for item in file_data]
        for new_item in api_data:
            if new_item.get("isin") not in existing_isins:
                file_data.append(new_item)

        file_repo.file_writer( "w", file_data)


