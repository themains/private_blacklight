library(ggplot2)

outcome_labels <- c(
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

tidy_models <- lapply(
  seq_along(models), 
  function(i) {
    broom::tidy(models[[i]]) %>%
      mutate(outcome = yvars_cum[i])
  }
)

# Combine into one long table
df_coef <- bind_rows(tidy_models) %>%
  mutate(
    term_clean = recode(term, !!!COEF_LABELS)
  )  %>%
  filter(term_clean %in% COEF_ORDER) %>% 
  mutate(
    term_clean = factor(term_clean, levels = rev(COEF_ORDER)),
    outcome = factor(outcome, levels = yvars_cum),
    outcome_label = recode(outcome, !!!outcome_labels),
    sig = p.value < 0.05
  )


coefplot = ggplot(
  df_coef, 
  aes(x = estimate, y = term_clean)
) +
  geom_errorbarh(
    aes(
      xmin = estimate - 1.96 * std.error,
      xmax = estimate + 1.96 * std.error
    ), 
    height = 0.2, 
    linewidth = 0.25,
    color = "gray90",
    alpha = 0.9,
  ) +
  # geom_point(size = 2.3) +
  geom_point(aes(color = sig), size = 1.4) +  
  geom_vline(
    xintercept = 0, 
    linetype = "dashed",
    color = "#800000",
    alpha = 0.6,
    linewidth = 0.5
  ) +
  facet_wrap(~ outcome_label, ncol = 4, scales = "free_x") +
  scale_color_manual(
    values = c(`TRUE` = "gray30", `FALSE` = "gray80"),
    labels = c(`TRUE` = "p < 0.05", `FALSE` = "n.s."),
    # name = "Significance"
  ) +  
  labs(
    x = "Estimate and 95% conf. int.",
    y = NULL,
    # title = "Estimated Effects Across Blacklist Tracking Outcomes"
  ) +
  theme_minimal(base_size = 5) +
  theme(
    # plot.title = element_text(face = "bold", size = 12, hjust = 0),
    axis.text = element_text(size = 8),
    axis.text.x = element_text(size = 8),
    strip.text = element_text(face = "bold", size = 10),
    panel.grid.major.y = element_blank(),
    panel.grid.minor = element_blank(),
    legend.position = "none"
  )

coefplot

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

savefig(plot=coefplot, filename = "demo_differences_coefplot", width = 16, height = 6)