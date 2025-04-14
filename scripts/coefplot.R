library(ggplot2)

outcome_coefplot_labels <- c(
  "bl_ddg_join_ads_rate" = "Ad trackers",
  "bl_third_party_cookies_rate" = "3rd Party Cookies",
  "bl_key_logging_rate" = "Keylogging",
  "bl_session_recording_rate" = "Session Recording",
  "bl_canvas_fingerprinting_rate" = "Canvas FP",
  "bl_fb_pixel_rate" = "FB Pixel",
  "bl_google_analytics_rate" = "Google Analytics",
  "who_trackers_per_page_load_rate" = "Trackers",
  "bl_ddg_join_ads" = "Ad trackers",
  "bl_third_party_cookies" = "3rd Party Cookies",
  "bl_key_logging" = "Keylogging",
  "bl_session_recording" = "Session Recording",
  "bl_canvas_fingerprinting" = "Canvas FP",
  "bl_fb_pixel" = "FB Pixel",
  "bl_google_analytics" = "Google Analytics",
  "who_trackers_per_page_load" = "Trackers"
)

process_model_list <- function(model_list, yvars) {
  # collect estimates into one long data for make_coefplot
  bind_rows(lapply(seq_along(model_list), function(i) {
    broom::tidy(model_list[[i]]) %>%
      mutate(outcome = yvars[i])
  })) %>%
    # tidy labels, sig, and orders
    mutate(
      term_clean = recode(term, !!!COEF_LABELS),
      outcome = factor(outcome, levels = yvars),
      outcome_label = recode(outcome, !!!outcome_coefplot_labels),
      sig = p.value < 0.05,
      term_clean = factor(term_clean, levels = rev(COEF_ORDER))
    ) %>%
    filter(term_clean %in% COEF_ORDER)
}

make_coefplot <- function(df) {
  ggplot(df, aes(x = estimate, y = term_clean)) +
    geom_errorbarh(
      aes(xmin = estimate - 1.96 * std.error, xmax = estimate + 1.96 * std.error),
      height = 0.25, 
      linewidth = 0.5, 
      color = "gray90", 
      alpha = 0.9
    ) +
    geom_point(aes(color = sig), size = 2.4) +
    geom_vline(
      xintercept = 0, 
      linetype = "dashed", 
      color = "#800000", 
      alpha = 0.6, 
      linewidth = 0.6
    ) +
    facet_wrap(~ outcome_label, ncol = 4, scales = "free_x") +
    scale_color_manual(values = c(`TRUE` = "gray30", `FALSE` = "gray80")) +
    labs(x = "Estimate and 95% conf. int.", y = NULL) +
    theme_minimal(base_size = 8.5) +  # overall font base
    theme(
      axis.text       = element_text(size = 13),   # axis tick labels
      axis.title.x    = element_text(size = 14),   # x-axis title
      strip.text      = element_text(face = "bold", size = 14),  # facet titles
      panel.grid.major.y = element_blank(),
      panel.grid.minor   = element_blank(),
      legend.position = "none"
    )
}


savefig <- function(
    plot, 
    filename, 
    width = 16, 
    height = 10, 
    dpi = 300, 
    path = "../figures"
) {
  # Build full paths
  pdf_path <- file.path(path, paste0(filename, ".pdf"))
  png_path <- file.path(path, paste0(filename, ".png"))
  
  # Save both formats
  ggsave(pdf_path, plot = plot, width = width, height = height, dpi = dpi)
  message("Saved to:\n- ", pdf_path)
  ggsave(png_path, plot = plot, width = width, height = height, dpi = dpi)
  message("Saved to:\n- ", png_path)
}


df_coef_rate  <- process_model_list(models, yvars_rate)
coefplot_rate <- make_coefplot(df_coef_rate)
savefig(coefplot_rate, "coefplot_demo_differences_rate")

df_coef_cum  <- process_model_list(models_cum, yvars_cum)
coefplot_cum <- make_coefplot(df_coef_cum)
savefig(coefplot_cum, "coefplot_demo_differences_cumulative")


