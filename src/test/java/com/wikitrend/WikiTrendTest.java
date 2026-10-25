package com.wikitrend;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

import org.apache.hadoop.fs.Path;
import org.junit.Test;

public class WikiTrendTest {

  private final PageviewParser.Record rec = new PageviewParser.Record();

  @Test
  public void parsesDesktopAndMobileWikipedia() {
    assertEquals(PageviewParser.Quality.ACCEPTED, PageviewParser.parse("en Elizabeth_II 41287 0", rec));
    assertEquals("en", rec.lang);
    assertEquals("Elizabeth_II", rec.title);
    assertEquals(41287, rec.views);

    assertEquals(PageviewParser.Quality.ACCEPTED, PageviewParser.parse("de.m Charles_III. 950 0", rec));
    assertEquals("de", rec.lang);
    assertEquals(PageviewParser.Quality.ACCEPTED, PageviewParser.parse("zh-min-nan Taiwan 3 0", rec));
  }

  @Test
  public void dropsOtherProjects() {
    assertEquals(PageviewParser.Quality.NON_WIKIPEDIA_PROJECT, PageviewParser.parse("en.d dog 10 0", rec));
    assertEquals(PageviewParser.Quality.NON_WIKIPEDIA_PROJECT, PageviewParser.parse("commons.m File:X.jpg 10 0", rec));
    assertEquals(PageviewParser.Quality.NON_WIKIPEDIA_PROJECT, PageviewParser.parse("en.m.voy Paris 10 0", rec));
  }

  @Test
  public void dropsNonArticlePages() {
    assertEquals(PageviewParser.Quality.NON_ARTICLE_PAGE, PageviewParser.parse("en Special:Search 999 0", rec));
    assertEquals(PageviewParser.Quality.NON_ARTICLE_PAGE, PageviewParser.parse("en.m Main_Page 999 0", rec));
    assertEquals(PageviewParser.Quality.NON_ARTICLE_PAGE, PageviewParser.parse("de Spezial:Suche 9 0", rec));
    // A colon inside a real article title is fine.
    assertEquals(PageviewParser.Quality.ACCEPTED, PageviewParser.parse("en Star_Wars:_Andor 99 0", rec));
  }

  @Test
  public void rejectsMalformedLines() {
    assertEquals(PageviewParser.Quality.MALFORMED, PageviewParser.parse("garbage", rec));
    assertEquals(PageviewParser.Quality.MALFORMED, PageviewParser.parse("en Foo notanumber 0", rec));
    assertEquals(PageviewParser.Quality.MALFORMED, PageviewParser.parse("en  12 0", rec));
  }

  @Test
  public void hourLabels() {
    assertEquals("2022-09-08T17", HourUtil.labelFromFileName("pageviews-20220908-170000.gz"));
    assertEquals("2022-09-08T00", HourUtil.labelFromFileName("pageviews-20220908-000000"));
    assertNull(HourUtil.labelFromFileName("projectviews-20220908-170000"));
    assertEquals("2022-09-08T17",
        HourUtil.labelFromPartitionPath(new Path("/wikitrend/agg/hour=2022-09-08T17/part-r-00000")));
    long h = HourUtil.toEpochHour("2022-09-08T17");
    assertEquals("2022-09-08T18", HourUtil.fromEpochHour(h + 1));
    assertEquals("2022-09-09T00", HourUtil.fromEpochHour(h + 7));
  }

  @Test
  public void detectsBreakingNewsSpike() {
    SpikeDetector d = new SpikeDetector(1000, 4.0, 3.0);
    SpikeDetector.Score s = new SpikeDetector.Score();
    long[] baseline = {5000, 5200, 4800, 5100, 4900, 5000};
    assertTrue(d.score(400000, baseline, baseline.length, s));
    assertEquals(5000, s.mean, 1e-9);
    assertTrue(s.z > 1000);
    assertEquals(395000, s.excess, 1e-9);
  }

  @Test
  public void ignoresNormalFluctuationAndSmallPages() {
    SpikeDetector d = new SpikeDetector(1000, 4.0, 3.0);
    SpikeDetector.Score s = new SpikeDetector.Score();
    long[] baseline = {5000, 5200, 4800, 5100, 4900, 5000};
    assertFalse(d.score(6000, baseline, baseline.length, s));          // +20 %: normal daily swing
    assertFalse(d.score(900, new long[] {0, 0, 0}, 3, s));             // below min views
  }

  @Test
  public void flatZeroBaselineDoesNotDivideByZero() {
    SpikeDetector d = new SpikeDetector(1000, 4.0, 3.0);
    SpikeDetector.Score s = new SpikeDetector.Score();
    assertTrue(d.score(5000, new long[] {0, 0, 0, 0}, 4, s));
    assertEquals(1.0, s.sigma, 1e-9);                                  // Poisson floor sqrt(0 + 1)
    assertTrue(Double.isFinite(s.z));
  }
}
