import os

import pandas as pd


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


# The panel was fielded June 2022 and profile.csv carries birthyr but no birth
# month, so age is accurate to +/-1 year: someone born 1957 is 65 if their
# birthday fell in Jan-Jun and 64 otherwise. Edges are set so each label's
# boundary cohort *can* be that age. pd.cut is right-closed, so "65+" is
# birthyr <= 1957 (65 for roughly half that cohort); the earlier edge of 1958
# admitted a cohort that was 63 or 64 in June 2022 and never 65.
#
# The result is that all five groups are their nominal age brackets: "<25" is
# birthyr 1998-2003, i.e. ages 18-24, since the youngest panelists (born 2003)
# turn 19 during the field period. 08_cps_benchmark.py cuts the CPS side to match.
AGE_BINS = [1929, 1957, 1972, 1987, 1997, 2003]
AGE_LABELS = ["65+", "50-64", "35-49", "25-34", "<25"]
AGE_ORDER = ["<25", "25-34", "35-49", "50-64", "65+"]


def agegroup_from_birthyr(birthyr):
    """Age group as of the June 2022 field period, from birth year."""
    return pd.Categorical(
        pd.cut(birthyr, bins=AGE_BINS, labels=AGE_LABELS),
        categories=AGE_ORDER,
        ordered=True,
    )


# Table 1's demographic categories: display order, and the long labels used in
# the manuscript floats. 08_cps_benchmark.py and 02_combine_yg_blacklight.ipynb
# both build Panel B, so these live here rather than in either of them.
DEMO_CAT_ORDER = [
    "Female",
    "Male",
    "White",
    "Hispanic",
    "Black",
    "Other",
    "Asian",
    "HS or Below",
    "Some college",
    "College",
    "Postgrad",
    "<25",
    "25-34",
    "35-49",
    "50-64",
    "65+",
]

DEMO_CAT_LABELS = {
    "<25": "$<$ 25 years old",
    "25-34": "25--34 years old",
    "35-49": "35--49 years old",
    "50-64": "50--64 years old",
    "65+": "65+ years old",
    "HS or Below": "High school diploma or below",
    "Some college": "Some college",
    "College": "College graduate",
    "Postgrad": "Postgraduate",
}

DEMO_VARS = ["gender_lab", "race_lab", "educ_lab", "agegroup_lab"]


def demo_counts(df_ind):
    """Table 1 Panel B: one row per demographic category with n and percent."""
    return (
        pd.concat([df_ind[v].value_counts() for v in DEMO_VARS])
        .reset_index(name="n")
        .rename(columns={"index": "cat"})
        .assign(
            cat=lambda df_: pd.Categorical(
                df_["cat"], categories=DEMO_CAT_ORDER, ordered=True
            )
        )
        .sort_values("cat")
        .reset_index(drop=True)
        .assign(perc=lambda df_: 100 * df_["n"] / len(df_ind))
    )


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
    "bl_google_analytics_rate": "Google Analytics (Remarketing)",
    "bl_third_party_cookies": "Third-Party Cookies",
    "bl_ddg_join_ads": "Ad Trackers",
    "bl_key_logging": "Keylogging",
    "bl_session_recording": "Session Recording",
    "bl_canvas_fingerprinting": "Canvas Fingerprinting",
    "bl_fb_pixel": "Facebook Pixel",
    "bl_google_analytics": "Google Analytics (Remarketing)",
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
