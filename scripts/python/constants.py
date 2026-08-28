import os


FP_WEB_MOBILE = "../data/yg/realityMine_web_mobile_2022-06-01_2022-06-30.csv"
FP_WEB_DESKTOP = "../data/yg/realityMine_web_desktop_2022-06-01_2022-06-30.csv"
FP_WEB = "../data/yg/realityMine_web_2022-06-01_2022-06-30.csv"
FP_YG_PROFILE = "../data/yg/profile.csv"
FP_BLACKLIGHT = "../data/blacklight_domain.csv"
FP_WHO = "../data/whotracksme_domain.csv"

filepaths = dict(
    web_mobile=FP_WEB_MOBILE,
    web_desktop=FP_WEB_DESKTOP,
    web=FP_WEB,
    yg_profile=FP_YG_PROFILE,
    blacklight=FP_BLACKLIGHT,
    who=FP_WHO,
)

print("Checking that all paths exist:")
print({key: os.path.exists(path) for key, path in filepaths.items()})


# also implies order
bl_measures = [
    "bl_ddg_join_ads_rate",
    "bl_third_party_cookies_rate",
    "bl_fb_pixel_rate",
    "bl_google_analytics_rate",
    "bl_session_recording_rate",
    "bl_key_logging_rate",
    "bl_canvas_fingerprinting_rate",
]

bl_measures_cumulative = [
    "bl_ddg_join_ads",
    "bl_third_party_cookies",
    "bl_fb_pixel",
    "bl_google_analytics",
    "bl_session_recording",
    "bl_key_logging",
    "bl_canvas_fingerprinting",
]

var_labels = {
    "tt_visits": "Total site visits",
    "tt_domains": "Total unique domains visited",
    # bl
    "bl_third_party_cookies_rate": "Third-Party Cookies",
    "bl_ddg_join_ads_rate": "Ad Trackers",
    "bl_key_logging_rate": "Keylogging",
    "bl_session_recording_rate": "Session Recording",
    "bl_canvas_fingerprinting_rate": "Canvas Fingerprinting",
    "bl_fb_pixel_rate": "Facebook Pixel",
    "bl_google_analytics_rate": "Google Analytics",
    "bl_third_party_cookies": "Third-Party Cookies",
    "bl_ddg_join_ads": "Ad Trackers",
    "bl_key_logging": "Keylogging",
    "bl_session_recording": "Session Recording",
    "bl_canvas_fingerprinting": "Canvas Fingerprinting",
    "bl_fb_pixel": "Facebook Pixel",
    "bl_google_analytics": "Google Analytics",
    # whotracksme
    "who_trackers_per_page_load": "Trackers/Page Load",
    "who_tracking_requests_per_page_load": "Tracking Requests/Page Load",
    "who_trackers_requests_all_requests": "% of requests to trackers",
    "who_trackers_per_page_load_rate": "Trackers/Page Load",
    "who_tracking_requests_per_page_load_rate": "Tracking Requests/Page Load",
    "who_trackers_requests_all_requests_rate": "% of requests to trackers",
    "who_data_saved_rate": "Data Saved",
    "who_advertising_rate": "Advertising",
    "who_audio_video_player_rate": "Audio/Video Player",
    "who_customer_interaction_rate": "Customer Interaction",
    "who_hosting_rate": "Hosting Services",
    "who_consent_management_rate": "Consent Management",
    "who_site_analytics_rate": "Site Analytics",
    "who_misc_rate": "Miscellaneous",
    "who_utilities_rate": "Utilities",
    "who_social_media_rate": "Social Media",
    "who_adult_advertising_rate": "Adult Advertising",
    "who_data_saved": "Data Saved",
    "who_advertising": "Advertising",
    "who_audio_video_player": "Audio/Video Player",
    "who_customer_interaction": "Customer Interaction",
    "who_hosting": "Hosting Services",
    "who_consent_management": "Consent Management",
    "who_site_analytics": "Site Analytics",
    "who_misc": "Miscellaneous",
    "who_utilities": "Utilities",
    "who_social_media": "Social Media",
    "who_adult_advertising": "Adult Advertising",
}


bl_al1 = [
    "bl_ddg_join_ads_al1",
    "bl_third_party_cookies_al1",
    "bl_canvas_fingerprinting_al1",
    "bl_session_recording_al1",
    "bl_key_logging_al1",
    "bl_fb_pixel_al1",
    "bl_google_analytics_al1",
]

bl_al10 = [
    "bl_ddg_join_ads_al10",
    "bl_third_party_cookies_al10",
    "bl_canvas_fingerprinting_al10",
    "bl_session_recording_al10",
    "bl_key_logging_al10",
    "bl_fb_pixel_al10",
    "bl_google_analytics_al10",
]

palette7 = [
    "#000000",  # black
    "#2f2f2f",  # very dark gray
    "#4d4d4d",  # dark gray
    "#6c6c6c",  # medium-dark gray
    "#8a8a8a",  # medium gray
    "#a8a8a8",  # medium-light gray
    "#c7c7c7",  # light gray
]

linestyles7 = ["-", "--", "-.", ":", (0, (1, 1)), (0, (5, 2)), (0, (3, 1, 1, 1))]
