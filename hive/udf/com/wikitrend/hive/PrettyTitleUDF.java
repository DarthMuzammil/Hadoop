package com.wikitrend.hive;

import org.apache.hadoop.hive.ql.exec.Description;
import org.apache.hadoop.hive.ql.exec.UDF;

/** Hive UDF: pretty_title('Death_and_state_funeral_of_Elizabeth_II') -> 'Death and state funeral of Elizabeth II' */
@Description(name = "pretty_title", value = "_FUNC_(title) - page title with underscores replaced by spaces")
public class PrettyTitleUDF extends UDF {
  public String evaluate(String title) {
    return title == null ? null : title.replace('_', ' ');
  }
}
