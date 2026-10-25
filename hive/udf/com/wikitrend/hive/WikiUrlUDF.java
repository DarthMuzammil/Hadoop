package com.wikitrend.hive;

import org.apache.hadoop.hive.ql.exec.Description;
import org.apache.hadoop.hive.ql.exec.UDF;

/** Hive UDF: wiki_url('en', 'Elizabeth_II') -> https://en.wikipedia.org/wiki/Elizabeth_II */
@Description(name = "wiki_url", value = "_FUNC_(lang, title) - link to the Wikipedia article")
public class WikiUrlUDF extends UDF {
  public String evaluate(String lang, String title) {
    if (lang == null || title == null) {
      return null;
    }
    return "https://" + lang + ".wikipedia.org/wiki/" + title;
  }
}
