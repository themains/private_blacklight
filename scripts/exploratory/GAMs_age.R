library(mgcv)
library(gratia)
library(ggplot2)

# run GAMs
gam_models <- lapply(yvars_rate, function(y) {
  gam(
    as.formula(paste0(
      y, " ~ s(birthyr) + gender_lab + race_lab + educ_lab"
    )),
    data = data,
    method = "REML"
  )
})
names(gam_models) <- yvars_rate


# tabulate df and pvals
nonlinear_summary <- lapply(gam_models, function(m) {
  s <- summary(m)
  list(
    edf = s$s.table[1, "edf"],
    pval = s$s.table[1, "p-value"]
  )
}) %>% 
  do.call(rbind, .) %>% 
  as.data.frame() %>%
  tibble::rownames_to_column("outcome") %>%
  mutate(
    edf = as.numeric(edf),
    pval = as.numeric(pval)
  )
nonlinear_summary


outcome_labels <- c(
  "bl_ddg_join_ads_rate" = "Ad Trackers",
  "bl_third_party_cookies_rate" = "3rd Party Cookies",
  "bl_fb_pixel_rate" = "Facebook Pixel",
  "bl_google_analytics_rate" = "Google Analytics",
  "bl_key_logging_rate" = "Keylogging",
  "bl_session_recording_rate" = "Session Recording",
  "bl_canvas_fingerprinting_rate" = "Canvas FP",
  "who_trackers_per_page_load_rate" = "Trackers (WhoTracksMe)"
)

plot_gam <- function(model, label) {
  # annotate edf and pval
  s <- summary(model)$s.table[1, ]
  edf_val <- round(s[["edf"]], 2)
  raw_p <- s[["p-value"]]
  pval_str <- if (raw_p < 0.001) "< .001" else sub("^0+", "", formatC(raw_p, digits = 3, format = "f"))
  annolabel <- paste(c(
    paste0("EDF = ", edf_val),
    paste0("p = ", pval_str)
  ), collapse = "\n")
  
  # get annot placement
  df_smooth <- gratia::smooth_estimates(model, smooth = "s(birthyr)")
  # y_max <- max(df_smooth$.estimate + 1.96 * df_smooth$.se, na.rm = TRUE)
  y_min <- min(df_smooth$.estimate - 1.96 * df_smooth$.se, na.rm = TRUE)
  
  # plot
  draw(
    model,
    select = "s(birthyr)",
    show_basis = FALSE,
    rug = FALSE
  ) +
    annotate("text",
             x = 2000,
             y = y_min,
             label = annolabel,
             hjust = 1,
             vjust = 0,
             size = 5) +
    labs(
      x = "Birth Year",
      y = paste0("Estimated exposure rate to\n", label),
      title = NULL,
      caption = NULL
    ) +
    theme_minimal(base_size = 14) +
    theme(
      plot.title = element_blank(),
      plot.caption = element_blank(),
      axis.title = element_text(size = 14),
      axis.text = element_text(size = 14),
      strip.text = element_text(size = 14),
      panel.grid.minor = element_blank(),
      panel.grid.major = element_line(size = 0.3),
      # shrink outer whitespace
      plot.margin = margin(0, 0, 0, 0)  
    )
}

for (y in names(gam_models)) {
  graph <- plot_gam(gam_models[[y]], label = outcome_labels[[y]])
  savefig(
    plot = graph,
    filename = paste0("gam_", y),
    width = 6.5,
    height = 4.5,
    dpi = 300,
    path = "../figures"
  )
}
