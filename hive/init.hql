-- Session init for every analysis query: database + custom UDFs (hive -i hive/init.hql ...)
USE wikitrend;
ADD JAR ${hivevar:UDF_JAR};
CREATE TEMPORARY FUNCTION wiki_url AS 'com.wikitrend.hive.WikiUrlUDF';
CREATE TEMPORARY FUNCTION pretty_title AS 'com.wikitrend.hive.PrettyTitleUDF';
