library(dplyr)
library(fixest)

data = read.csv("../data/combined_yg_bl_who.csv") %>% 
  mutate(
    women = ifelse(gender_lab == "Female", 1, 0),
    tt_visits_scaled = scales::rescale(tt_visits, to = c(0, 1)),
    tt_domains_scaled = scales::rescale(tt_domains, to = c(0, 1)),
  )

head(data)

runreg <- function(
    yvar,
    data,
    addFE = NULL,
    addZ = NULL,
    noisy = TRUE
    ) {
 
  if (noisy) cat("Running regression for:", yvar, "\n")

    # =======================================================
  # Build specification
  default_covariates <- paste(
    "i(gender_lab, ref = 'Male')",
    "i(race_lab, ref = 'White')",
    "i(educ_lab, ref = 'HS or Below')",
    "i(agegroup_lab, ref = '<25')",
    sep = " + "
  )
  
  if (!is.null(addZ)) {
    extra_covariates <- paste(addZ, collapse = " + ")
    covariates <- paste(default_covariates, extra_covariates, sep = " + ")
  } else {
    covariates <- default_covariates
  }
  
  fe_str <- ""
  if (!is.null(addFE)) {
    fe_str <- paste(addFE, collapse = " + ")
  }
  
  fml <- as.formula(
    if (fe_str == "") {
      paste(yvar, "~", covariates)
    } else {
      paste(yvar, "~", covariates, "|", fe_str)
    }
  )
  
  if (noisy) cat("Formula:", format(fml), "\n")
  
  model <- feols(fml, data = data, vcov = "HC1")
  return(model)
  
}

# coef labels -------------------------------------------------------------
COEF_LABELS = c(
  "gender_lab::Female" = "Woman",
  "race_lab::Black" = "Race: African American",
  "race_lab::White" = "Race: White",
  "race_lab::Asian" = "Race: Asian",
  "race_lab::Hispanic" = "Race: Hispanic",
  "race_lab::Other" = "Race: Other",
  "educ_lab::College" = "Educ: College",
  "educ_lab::Postgrad" = "Educ: Postgraduate",
  "educ_lab::Some college" = "Educ: Some college",
  "agegroup_lab::<25" = "Age: 18--25",
  "agegroup_lab::25-34" = "Age: 25--34",
  "agegroup_lab::35-49" = "Age: 35--49",
  "agegroup_lab::50-64" = "Age: 50--64",
  "agegroup_lab::65+" = "Age: 65+",
  age_mc = "Age",
  age_scaled="Age (scaled)",
  "I(age_scaled^2)" = "Age$^2$ (scaled)",
  age = "Age",
  "I(age_mc^2)" = "Age$^2$ (scaled)"
)

COEF_ORDER = c(
  "Woman",
  "Race: African American",
  "Race: Asian",
  "Race: Hispanic",
  "Race: Other",
  "Educ: Some college",
  "Educ: College",
  "Educ: Postgraduate",
  "Age: 25--34",
  "Age: 35--49",
  "Age: 50--64",
  "Age: 65+",
  "Constant"
)


col_headers <- c(
  "Ad",
  "Cookies",
  "FB Pixel",
  "GA",
  "Keylogger",
  "Session rec",
  "Canvas FP",
  "Trackers"      
)


yvars_cum <- c(
  "bl_ddg_join_ads",
  "bl_third_party_cookies",
  "bl_fb_pixel",
  "bl_google_analytics",
  "bl_key_logging",
  "bl_session_recording",
  "bl_canvas_fingerprinting",
  "who_trackers_per_page_load"
)

models_cum <- lapply(
  yvars_cum, 
  function(y) {runreg(yvar = y, data = data)}
)

etable(
  models_cum,
  digits = 2,
  digits.stats = 2,
  dict = COEF_LABELS,
  order = COEF_ORDER,
  signif.code = c("***"=0.01, "**"=0.05, "*"=0.10),
  fitstat = c("my", "r2", "n"),
  se.row = FALSE,
  depvar=FALSE,
  headers = col_headers,
  tex = TRUE,
  adjustbox=TRUE,
  file = "../tables/demo_differences_cum_exposure.tex",
  replace=TRUE,  
  style.tex = style.tex("aer")
)
cat(readLines("../tables/demo_differences_cum_exposure.tex"), sep = "\n")


yvars <- c(
  "bl_ddg_join_ads_rate",
  "bl_third_party_cookies_rate",
  "bl_fb_pixel_rate",
  "bl_google_analytics_rate",
  "bl_key_logging_rate",
  "bl_session_recording_rate",
  "bl_canvas_fingerprinting_rate",
  "who_trackers_per_page_load_rate"
)


models <- lapply(
  yvars, 
  function(y) {runreg(yvar = y, data = data)}
)

etable(
  models,
  digits = 2,
  digits.stats = 2,
  dict = COEF_LABELS,
  order = COEF_ORDER,
  signif.code = c("***"=0.01, "**"=0.05, "*"=0.10),
  fitstat = c("my", "r2", "n"),
  se.row = FALSE,
  depvar=FALSE,
  headers = col_headers,
  tex = TRUE,
  adjustbox=TRUE,
  file = "../tables/demo_differences_exposure_rate.tex",
  replace=TRUE,  
  style.tex = style.tex("aer")
)
cat(readLines("../tables/demo_differences_exposure_rate.tex"), sep = "\n")
