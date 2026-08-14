<script lang="ts">
  import { SITE_NAME, SITE_DESCRIPTION, pageTitle } from "./seo";

  let {
    title,
    description = SITE_DESCRIPTION,
    path,
    origin,
    robots,
    jsonLd,
  }: {
    title: string;
    description?: string;
    path: string;
    origin: string;
    robots?: string;
    jsonLd?: unknown;
  } = $props();

  const fullTitle = pageTitle(title);
  const url = `${origin}${path}`;
  const jsonLdString = jsonLd
    ? JSON.stringify(jsonLd).replace(/</g, "\\u003c")
    : undefined;
</script>

<svelte:head>
  <title>{fullTitle}</title>
  <meta name="description" content={description} />
  <link rel="canonical" href={url} />
  {#if robots}
    <meta name="robots" content={robots} />
  {/if}
  <meta property="og:type" content="website" />
  <meta property="og:site_name" content={SITE_NAME} />
  <meta property="og:title" content={fullTitle} />
  <meta property="og:description" content={description} />
  <meta property="og:url" content={url} />
  <meta name="twitter:card" content="summary" />
  {#if jsonLdString}
    {@html `<script type="application/ld+json">${jsonLdString}</script>`}
  {/if}
</svelte:head>
