package com.wikitrend;

import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import org.apache.hadoop.fs.Path;

/**
 * Helpers for the hour labels used throughout the pipeline.
 *
 * Wikimedia publishes one file per hour, named {@code pageviews-YYYYMMDD-HH0000[.gz]}.
 * Inside the pipeline an hour is written as the label {@code YYYY-MM-DDTHH} (e.g. 2022-09-08T17),
 * which is also used as the Hive partition value ({@code hour=2022-09-08T17}).
 * For arithmetic (baseline windows) we use "epoch hours": hours since 1970-01-01T00 UTC.
 */
public final class HourUtil {

  private static final Pattern FILE_NAME =
      Pattern.compile("pageviews-(\\d{4})(\\d{2})(\\d{2})-(\\d{2})\\d{4}(\\.gz)?");
  private static final DateTimeFormatter LABEL = DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH");

  public static final String PARTITION_PREFIX = "hour=";

  private HourUtil() {}

  /** "pageviews-20220908-170000.gz" -> "2022-09-08T17", or null if the name does not match. */
  public static String labelFromFileName(String name) {
    Matcher m = FILE_NAME.matcher(name);
    if (!m.matches()) {
      return null;
    }
    return m.group(1) + "-" + m.group(2) + "-" + m.group(3) + "T" + m.group(4);
  }

  /** ".../hour=2022-09-08T17/part-r-00000" -> "2022-09-08T17", or null if not inside a partition. */
  public static String labelFromPartitionPath(Path file) {
    for (Path p = file.getParent(); p != null; p = p.getParent()) {
      String name = p.getName();
      if (name.startsWith(PARTITION_PREFIX)) {
        return name.substring(PARTITION_PREFIX.length());
      }
    }
    return null;
  }

  public static long toEpochHour(String label) {
    LocalDateTime t = LocalDateTime.parse(label, LABEL);
    return t.toEpochSecond(ZoneOffset.UTC) / 3600L;
  }

  public static String fromEpochHour(long epochHour) {
    return LocalDateTime.ofEpochSecond(epochHour * 3600L, 0, ZoneOffset.UTC).format(LABEL);
  }
}
