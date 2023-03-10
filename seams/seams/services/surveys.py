import os
import streamlit as st
import re
from seams.datastorage import DataStore, YamlStorage
from seams.bgs_tools import get_h3_geohash, reproject_coordinates
from typing import Dict, List, Any, Callable
from itertools import count
from dataclasses import dataclass, field
from datetime import datetime 
import pandas as pd


# Globals

APP_DIRPATH = st.session_state['APP_DIRPATH']
DATA_DIRPATH = st.session_state['DATA_DIRPATH']
SERVICES_DIRPATH = st.session_state['SERVICES_DIRPATH']
ASSETS_DIRPATH = st.session_state['ASSETS_DIRPATH']
APP_SERVICES_YAML = st.session_state['APP_SERVICES_YAML']
USERS_FILEPATH = st.session_state['USERS_FILEPATH']
SURVEY_FILEPATH = os.path.join(DATA_DIRPATH, 'survey.yaml')
if 'SURVEY_FILEPATH' not in st.session_state:
    st.session_state['SURVEY_FILEPATH'] = SURVEY_FILEPATH

#
ds_survey = DataStore(YamlStorage(file_path=SURVEY_FILEPATH))


def show_new_user_form(ds_users:DataStore):
    new_user = None

    if 'affiliations' in st.session_state:
        affiliations = st.session_state['affiliations']
    else:
        affiliations = None

    userForm = st.form(key='userForm', clear_on_submit=True)
    with userForm:
        st.write('**Create a new user**')
        name = st.text_input("Name:", placeholder='user name')
        # email = st.text_input("Email:", placeholder='user email address')
        affiliations = st.session_state['affiliations']

        if affiliations:
            affiliation = st.selectbox(
                label='Affilation:', 
                options=[ f'{k} - {v}' for k,v in affiliations.items()])
        else:
            affiliation = st.text_input("Affiliation", placeholder='user affiliation')


        apply_new_user_btn = st.form_submit_button(label='apply')

        if apply_new_user_btn:
            if not name or not affiliation:
                st.error("All fields are required.")            
            else:
                try:
                    new_user = {'name': name,
                                'affiliation': affiliation}
                    ds_users.storage_strategy.data['users'].append(new_user)
                    ds_users.store_data(data=ds_users.storage_strategy.data)
                    st.session_state['new_user'] = new_user
                    
                    #
                    
                except Exception as e:
                    st.error(e)
                finally:
                    
                    st.success(f"**User:** `{new_user}` registered!")
                    
                    return new_user
        


def has_media(stations_dict:dict, media)->dict:
    """Function checks wether all the `siteNames` in the `stations_dict` has a `media` dictionary, 
    if it does not it adds the `media` key with a new dictionary with media as key and value an empty list, else
    adds a new dictionary with media as key and value an empty list.


    Args:
        stations_dict (dict): _description_
        media (str): _description_

    Returns:
        dict: _description_
    """
    for siteName in stations_dict:
        media_key = f'{media}'
        if 'media' not in stations_dict[siteName]:
            stations_dict[siteName]['media'] ={media_key: []}
        else:
            if media_key not in stations_dict[siteName]['media']: 
                stations_dict[siteName]['media'][media_key] = []
    return stations_dict

def update_session_state(key:str, value:Any)->bool:
    if key not in st.session_state:
        st.session_state[key] = value
    else:
        st.session_state[key] = value
    return True

def get_session_state_value(key:str):
    """If `key` exist in `st.session_state` return its value else None

    Args:
        key (str): Key to search in st.session_state

    Returns:
        _type_: _description_
    """
    if key in st.session_state:
        return st.session_state[key]
    

def show_surveyForm(
    delimeters:dict[str, str] = {'tab':'\t', 'comma':',', 'semicolon':';'}, 
    decimals:dict[str, str] = {'point':'.', 'comma':','}, 
    encodings:list[str] = ['utf-8', 'windows-1252'], 
    ):

    stations_df = None
    videos_df = None
    stations_dict = {}
    media = 'photos'
    survey_dict = {}

    with st.container():
        h1_col, _ , msg_col = st.columns(3)
        with h1_col:
            st.subheader('Survey details')
        with msg_col:
            priority_message = st.empty()
            missing_keys = check_required_session_keys()
            if len(missing_keys)> 0:
                #priority_message.success('Survey initialization is done!')
            #else:
                priority_message.warning(f'**Required**: {missing_keys}')
        
        top_col1,  top_col2, top_col3, top_col4  = st.columns([1,1,1,2])
        with top_col1:
            if 'surveyID' in st.session_state:
                session_id = st.session_state['surveyID'] if st.session_state['surveyID'] else None
                surveyID = st.text_input(
                    label='**SurveyID:**', placeholder='Write the surveyID', value=session_id)
            else:
                surveyID = st.text_input(label='**SurveyID:**', placeholder='Write the surveyID')

            if surveyID:
                update_session_state(key='surveyID', value=surveyID)
                # Check survey datastorage for data
                data = ds_survey.storage_strategy.data
                data['current_surveyID'] = surveyID

                if 'surveys' not in data:
                    data['surveys'] = {}
                if surveyID not in data['surveys']:
                    data['surveys'][surveyID] = {}

                # Saving to datastorage
                ds_survey.store_data(data=data)

        with top_col2:
            media = st.radio(label = '**Media:**', options=['photos', 'video'], index=0, horizontal=True)
            if media:
                st.session_state['media'] = media
        
        with st.form("survey form"):
            files_col1, files_col2 = st.columns([1,1])

            with files_col1:
                stationsFile_bytesio = st.file_uploader(label='**Stations file:**', type=['csv', 'tsv'])
            
            if media == 'video':
                with files_col2:
                    videosFile_bytesio = st.file_uploader(label='**Videos file:**', type=['csv', 'tsv'])
            else:
                videosFile_bytesio = None            

            col_delimiter, col_decimal, col_encoding, _, col_nstations = st.columns([1,1,1,1,1])
                    
            with col_delimiter:
                delimeter = st.selectbox(label='**delimeter:**', options=delimeters)
            with col_decimal:
                decimal = st.selectbox(label='**decimal:**', options=decimals)
            with col_encoding:
                encoding = st.selectbox(label='**encoding:**', options=encodings)

            apply_media_btn = st.form_submit_button(label='load files')

            # if apply_media_btn:
            missing_keys = check_required_session_keys()

            
            expander_col1, expander_col2 = st.columns([1,1])
            with expander_col1:
                stations_expander = st.expander(label= f'**Stations table**')
            with expander_col2:
                videos_expander = st.expander(label='**Videos table**')
            

            if delimeter and decimal and encoding:
                _delimeter = delimeters[delimeter]
                _decimal = decimals[decimal]        

                if stationsFile_bytesio is not None:
                    update_session_state(key='surveyID', value=stationsFile_bytesio.name[:-4].split('__')[0])
                    
                    with st.spinner(text='loading stations ...'):
                        stations_df = pd.read_csv(
                            stationsFile_bytesio,
                            delimiter = _delimeter,
                            decimal= _decimal, 
                            encoding=encoding)

                    if isinstance(stations_df, pd.DataFrame):
                        stations_dict = get_stations_data(df=stations_df)
                        if stations_dict and surveyID:
                            n_stations = len(stations_dict)
                            update_session_state('n_stations', value=n_stations)

                            #data =  ds_survey.storage_strategy.data

                            if 'surveys' not in ds_survey.storage_strategy.data:
                                ds_survey.storage_strategy.data['surveys'] = {}                        
                            if surveyID and surveyID not in ds_survey.storage_strategy.data['surveys']:
                                ds_survey.storage_strategy.data['surveys'][surveyID] = {'stations':{}}
                            #
                                
                            ds_survey.storage_strategy.data['surveys'][surveyID]['n_stations'] = n_stations
                            
                            stations_dict = has_media(stations_dict=stations_dict, media=media)
                            ds_survey.storage_strategy.data['surveys'][surveyID]['stations'] = stations_dict
                            
                            # save to datastorage
                            ds_survey.store_data(data=ds_survey.storage_strategy.data)
                            
                            with top_col3:
                                st.metric('**n stations**', value= n_stations)

                if videosFile_bytesio is not None:
                    with st.spinner('Loading videos ...'):
                        videos_df = pd.read_csv(
                            videosFile_bytesio,
                            delimiter = _delimeter,
                            decimal= _decimal, 
                            encoding=encoding)
            
            with stations_expander:
                if isinstance(stations_df, pd.DataFrame):
                    st.dataframe(stations_df)                    

                with videos_expander:
                    if isinstance(videos_df, pd.DataFrame):
                        st.dataframe(videos_df)                        
                        videos_dict = get_videos_per_station(                            
                            videos_df=videos_df, 
                            callback=error_callback, 
                            )
                        update_session_state(key='videos_dict', value=videos_dict)
                        if surveyID and surveyID in ds_survey.storage_strategy.data['surveys']:
                            # ds_survey.storage_strategy.data['surveys'][surveyID]['videos'] = videos_dict
                            for s, v in videos_dict.items():
                                ds_survey.storage_strategy.data['surveys'][surveyID]['stations'][s]['media']['video'] = v
                            
                            # save to datastore
                            ds_survey.store_data(data=ds_survey.storage_strategy.data)
                            



            with top_col4:
                if stations_dict is not None:
                    if 'stations_interpreted' not in st.session_state:
                        stations_to_interpret = stations_dict
                    elif len(st.session_state['stations_interpreted']) > 0:
                        stations_to_interpret = {k:v for k,v in stations_dict.items() if k not in st.session_state['stations_interpreted']}
                    else:
                        stations_to_interpret = stations_dict
               
                    current_station = st.selectbox( 
                        '**Choose station for seafloor interpretation:**',
                        options=stations_to_interpret)
                    
                    if current_station:
                        ds_survey.storage_strategy.data['current_station'] = current_station                     
                        ds_survey.store_data(data=ds_survey.storage_strategy.data)

                        update_session_state(
                            key='current_station',
                            value=current_station
                            )
                        
                #TODO: depreciate the following        
                if surveyID:
                    with top_col3:                        
                        survey_dict[surveyID] = stations_dict
                        update_session_state(key='survey_dict', value=survey_dict)                

                    if 'stations_dict' not in st.session_state:
                        update_session_state('stations_dict', value=stations_dict)                  

                else:
                    st.error("All fields are required.")
                
def has_all_required_columns(
    file_columns:list, 
    required_colnames: list):
    
    valid_cols = [col for col in file_columns if col in required_colnames]
    if len(valid_cols) == len(required_colnames):
        return True
    else:
        return False

def error_callback(error:str):
    st.error(error)

def videos_generator(subset:pd.DataFrame):
    pass
    

def get_videos_per_station(videos_df: pd.DataFrame, callback: Callable = error_callback) -> dict:
    required_colnames = ['siteName', 'filename', 'filepath']
    if not set(required_colnames).issubset(videos_df.columns):
        error_message = f"Missing required column names for video file. Required columns: {required_colnames}"
        callback(error_message)
        raise ValueError(error_message)        
    _videos = {}
    for siteName, subset in videos_df.groupby('siteName'):
        _videos[siteName] = dict(zip(subset['filename'], subset['filepath']))       
    return _videos

            

def get_stations_data(
    df:pd.DataFrame, 
    required_colnames: list  = [
        'siteName', 
        'decimalLatitude',
        'decimalLongitude',
        'geodeticDatum',
        'countryCode',
        'eventDate',
        'maximumDepthInMeters'
        ]):

    file_columns = df.columns.values.tolist()
    file_input_valid = has_all_required_columns(
        file_columns=file_columns, required_colnames=required_colnames)

    if file_input_valid:
        r = re.compile("measurementType", re.IGNORECASE)
        # regex to find all the columns names that matches `measurementType` at any place in the string.
        measurementType_cols = sorted(list(filter(r.search, file_columns )))
       
        results_list = []
        for _, row in df.iterrows():
            row_dict= {}
            for col in required_colnames:
                row_dict[col] = row.get(col)

            measurements = {}
            for col in measurementType_cols:
                measurements[col] = row[col]
                       
            if len(measurements)>0:
                row_dict['measurementTypes'] = measurements
                
            results_list.append(row_dict)

        stations_dict = {item['siteName']: item for item in results_list}
        
        return stations_dict
    

    

def check_required_session_keys():
    """To be depreciated in favour of the data store

    Returns:
        _type_: _description_
    """

    required_keys = []
    missing_keys = []

    media = get_session_state_value('media')
    
    # quick fix as there is a refresh lag
    if media == 'video':
        required_keys =  ['user', 'surveyID', 'media', 'current_station', 'survey_dict', 'videos_dict']
    if media == 'photos':
        required_keys =  ['user', 'surveyID', 'media', 'current_station', 'survey_dict']

 
    for k in required_keys:
        if k not in st.session_state or not st.session_state[k] or st.session_state[k]=="":
            # Making it user friendly reading of varaiables.
            if k == 'current_station':
                k = 'station'
            if k == 'survey_dict':
                k = 'stations file'
            if k == 'videos_dict':
                k = 'videos file'
            missing_keys.append(k)
    return missing_keys

def ds_get_current_user():
    """ Returns the current user from the data_store

    Returns:
        str: Saved current user from previous session
    """
    if 'current_user' in ds_survey.storage_strategy.data:
        return ds_survey.storage_strategy.data['current_user']
#

def main():
    """
    Main function to display the header status, list of users, and allow creating a new user
    """
    
    ds_users = DataStore(YamlStorage(file_path=USERS_FILEPATH))
    users_list = [user['name'] for user in ds_users.storage_strategy.data['users'] ]

    with st.container():
        user_col1, user_col2 = st.columns(2)
        with user_col1:
            _user = ds_get_current_user()
            # get the index of the current user in the user_list
            idx = users_list.index(_user) if _user in users_list else None
            
            user = st.selectbox(
                "**Select a user:**", ['< new user >'] + users_list,
                index= idx + 1 if idx else 0
                )
            st.session_state['user'] = user
            

            if user == '< new user >':
                with user_col2:
                    new_user = show_new_user_form(ds_users)
                user_col1.button('refresh')


        if user and user != '< new user >':
            ds_survey.storage_strategy.data['current_user'] = user
            st.session_state['user'] = user


        #  Shows the survey form
        show_surveyForm()

    show_data_expander = st.expander(label='**show data**', expanded=False)
    with show_data_expander:
        st.write(ds_survey.storage_strategy.data)
                
        
# ----------

main()
