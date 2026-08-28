# Convert the restricted RealityMine visit file to parquet.
#
# Dataverse ships a 2 GB CSV (doi:10.7910/DVN/VIV4TS, file 6797139). The
# pipeline reads four of its 27 columns, so storing it columnar costs 183 MB
# instead of 2,025 and makes those reads faster rather than slower. Run once
# after downloading; the CSV can then be discarded.
suppressMessages({library(arrow); library(data.table)})


src <- file.path("data", "yg", "realityMine_web_2022-06-01_2022-06-30.csv")
dst <- sub("\\.csv$", ".parquet", src)
if (!file.exists(src)) stop("missing ", src)

# session_start_time is read as text: parsing it here would bake in a timezone
# the consumers should choose for themselves.
d <- fread(src, showProgress = FALSE, colClasses = list(character = "session_start_time"))
write_parquet(d, dst, compression = "zstd")

chk <- read_parquet(dst)
stopifnot(nrow(chk) == nrow(d), identical(sort(names(chk)), sort(names(d))))
for (k in names(d)) if (!isTRUE(all.equal(d[[k]], chk[[k]])))
    stop("column changed in conversion: ", k)
message(sprintf("%s -> %s (%.0f MB -> %.0f MB); all %d columns identical",
                basename(src), basename(dst),
                file.size(src) / 1e6, file.size(dst) / 1e6, ncol(d)))
