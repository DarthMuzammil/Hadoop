package com.wikitrend;

import java.util.Arrays;
import java.util.HashSet;
import java.util.Set;
import java.util.regex.Pattern;

/**
 * Parses and cleans one line of a Wikimedia pageview dump.
 *
 * Line format (space separated): {@code domain_code page_title count_views total_response_size}
 * e.g. {@code en.m Elizabeth_II 412873 0}.
 *
 * Cleaning rules:
 *  - keep only Wikipedia projects: "xx" (desktop) and "xx.m" (mobile); both are merged into language "xx".
 *    Other projects (wiktionary "en.d", wikibooks "en.b", commons, wikidata, ...) are dropped.
 *  - drop non-article pages (Special:, Talk:, File:, ...) and main pages, which are navigation, not news.
 */
public final class PageviewParser {

  /** Why a line was accepted or rejected. Used as Hadoop counters for the data-quality report. */
  public enum Quality {
    ACCEPTED, MALFORMED, NON_WIKIPEDIA_PROJECT, NON_ARTICLE_PAGE
  }

  /** Mutable holder, reused across calls to avoid allocating per record inside the mapper. */
  public static final class Record {
    public String lang;
    public String title;
    public long views;
  }

  // Language codes look like "en", "de", "zh-yue", "zh-min-nan". This also rejects "commons", "meta", "species".
  private static final Pattern LANG = Pattern.compile("[a-z]{2,3}(-[a-z0-9]+)*");

  private static final Set<String> NON_ARTICLE_NAMESPACES = new HashSet<>(Arrays.asList(
      "Special", "Talk", "User", "User_talk", "Wikipedia", "Wikipedia_talk", "File", "File_talk",
      "MediaWiki", "MediaWiki_talk", "Template", "Template_talk", "Help", "Help_talk", "Category",
      "Category_talk", "Portal", "Portal_talk", "Draft", "Draft_talk", "Module", "Module_talk",
      "TimedText", "Image", "Media", "Book", "Project",
      // frequent localised namespaces (de, es, fr, it, ru, ja, pl, pt, nl)
      "Spezial", "Benutzer", "Datei", "Diskussion", "Kategorie", "Vorlage", "Hilfe",
      "Especial", "Usuario", "Archivo", "Categoría", "Plantilla", "Ayuda",
      "Spécial", "Utilisateur", "Fichier", "Catégorie", "Modèle", "Aide", "Discussion",
      "Speciale", "Utente", "Categoria", "Aiuto",
      "Служебная", "Участник", "Файл", "Категория", "Шаблон", "Справка", "Обсуждение",
      "特別", "利用者", "ファイル", "Specjalna", "Wikipedysta", "Plik", "Kategoria",
      "Predefinição", "Usuário", "Ficheiro", "Speciaal", "Gebruiker", "Bestand", "Categorie"));

  private static final Set<String> MAIN_PAGES = new HashSet<>(Arrays.asList(
      "-", "Main_Page", "Wikipedia:Hauptseite", "Wikipédia:Accueil_principal", "Wikipedia:Portada",
      "Pagina_principale", "Заглавная_страница", "メインページ", "Wikipedia:Strona_główna",
      "Wikipédia:Página_principal", "Hoofdpagina", "Main_page", "Index.html"));

  private PageviewParser() {}

  public static Quality parse(String line, Record out) {
    // Manual split is noticeably faster than String.split for ~100M lines/day.
    int s1 = line.indexOf(' ');
    if (s1 <= 0) {
      return Quality.MALFORMED;
    }
    int s2 = line.indexOf(' ', s1 + 1);
    if (s2 <= s1 + 1) {
      return Quality.MALFORMED;
    }
    int s3 = line.indexOf(' ', s2 + 1);
    if (s3 < 0) {
      s3 = line.length();
    }

    String domain = line.substring(0, s1);
    String lang;
    if (domain.endsWith(".m")) {
      lang = domain.substring(0, domain.length() - 2);
    } else {
      lang = domain;
    }
    if (!LANG.matcher(lang).matches()) {
      return Quality.NON_WIKIPEDIA_PROJECT;
    }

    long views;
    try {
      views = Long.parseLong(line.substring(s2 + 1, s3));
    } catch (NumberFormatException e) {
      return Quality.MALFORMED;
    }
    if (views <= 0) {
      return Quality.MALFORMED;
    }

    String title = line.substring(s1 + 1, s2);
    if (!isArticle(title)) {
      return Quality.NON_ARTICLE_PAGE;
    }

    out.lang = lang;
    out.title = title;
    out.views = views;
    return Quality.ACCEPTED;
  }

  static boolean isArticle(String title) {
    if (MAIN_PAGES.contains(title)) {
      return false;
    }
    int colon = title.indexOf(':');
    // A colon is only a namespace separator if the prefix is a known namespace; "Star_Wars:_Andor" is an article.
    return colon <= 0 || !NON_ARTICLE_NAMESPACES.contains(title.substring(0, colon));
  }
}
