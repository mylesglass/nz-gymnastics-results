<script lang="ts">
  import { onMount } from "svelte";
  import { uploadFile, importFromUrl, saveAliases, checkAuthStatus } from "$lib/api";
  import type { EventSummary } from "$lib/api";
  import { currentUser, authConfigured } from "$lib/auth";

  type UploadSource = { kind: "file"; file: File } | { kind: "url"; url: string };

  interface UploadItem {
    label: string;
    status: "uploading" | "success" | "error";
    id?: number;
    name?: string;
    gymnast_count?: number;
    score_count?: number;
    club_count?: number;
    errorMessage?: string;
    errorDetails?: string[];
    errorRaw?: string;
  }

  let uploads = $state<UploadItem[]>([]);
  let uploading = $state(false);
  let loggedIn = $state(false);
  let authCfg = $state(false);
  let urlInput = $state("");

  // Club mapping dialog state
  let clubDialog = $state<{ source: UploadSource; unknown: string[]; known: string[] } | null>(null);
  let clubMappings = $state<Record<string, string>>({});
  let remainingSources = $state<UploadSource[]>([]);

  onMount(() => {
    checkAuthStatus()
      .then((s) => authConfigured.set(s.configured))
      .catch(() => {});
    const unsub1 = currentUser.subscribe((v) => (loggedIn = v !== null));
    const unsub2 = authConfigured.subscribe((v) => (authCfg = v));
    return () => {
      unsub1();
      unsub2();
    };
  });

  function labelFor(source: UploadSource): string {
    return source.kind === "file" ? source.file.name : source.url;
  }

  async function uploadSource(source: UploadSource, allowUnknown = false): Promise<EventSummary> {
    return source.kind === "file" ? uploadFile(source.file, allowUnknown) : importFromUrl(source.url, allowUnknown);
  }

  async function handleSources(sources: UploadSource[]) {
    if (sources.length === 0) return;

    uploading = true;
    uploads = [];

    for (let i = 0; i < sources.length; i++) {
      const source = sources[i];
      uploads = [...uploads, { label: labelFor(source), status: "uploading" }];

      try {
        const ev = await uploadSource(source);
        const idx = uploads.findIndex((u) => u.label === labelFor(source) && u.status === "uploading");
        if (idx !== -1) {
          uploads[idx] = {
            label: labelFor(source),
            status: "success",
            id: ev.id,
            name: ev.name,
            gymnast_count: ev.gymnast_count,
            score_count: ev.score_count,
            club_count: ev.club_count,
          };
          uploads = [...uploads];
        }
      } catch (err) {
        const ce = err as Error & { _clubConflict?: boolean; unknown_clubs?: string[]; known_clubs?: string[] };
        if (ce._clubConflict && ce.unknown_clubs && ce.known_clubs) {
          const idx = uploads.findIndex((u) => u.label === labelFor(source) && u.status === "uploading");
          if (idx !== -1) uploads.splice(idx, 1);
          uploading = false;
          remainingSources = sources.slice(i + 1);
          const mappings: Record<string, string> = {};
          for (const u of ce.unknown_clubs) mappings[u] = ce.known_clubs[0] || u;
          clubMappings = mappings;
          clubDialog = { source, unknown: ce.unknown_clubs, known: ce.known_clubs };
          break;
        }
        const text = String(err);
        let errorMessage: string | null = null;
        let errorDetails: string[] = [];
        let errorRaw = text;
        try {
          const parsed = JSON.parse(text);
          if (parsed.errors && Array.isArray(parsed.errors)) {
            errorDetails = parsed.errors;
            errorMessage = parsed.message || "Upload failed";
          } else if (parsed.detail) {
            errorMessage = parsed.detail;
          } else {
            errorMessage = text;
          }
        } catch {
          const msg = err instanceof Error ? err.message : text;
          errorMessage = msg || text;
        }
        const idx = uploads.findIndex((u) => u.label === labelFor(source) && u.status === "uploading");
        if (idx !== -1) {
          uploads[idx] = {
            label: labelFor(source),
            status: "error",
            errorMessage: errorMessage ?? undefined,
            errorDetails,
            errorRaw,
          };
          uploads = [...uploads];
        }
      }
    }

    uploading = false;
  }

  function handleFiles(fileList: FileList | File[]) {
    const files = Array.from(fileList).filter((f) => f.name.endsWith(".json"));
    if (files.length === 0) return;
    handleSources(files.map((file) => ({ kind: "file" as const, file })));
  }

  async function handleUrl() {
    const urls = urlInput
      .split(/\r?\n/)
      .map((u) => u.trim())
      .filter((u) => u.length > 0);
    if (urls.length === 0) return;
    urlInput = "";
    await handleSources(urls.map((url) => ({ kind: "url" as const, url })));
  }

  async function saveAndRetry() {
    if (!clubDialog) return;
    try {
      await saveAliases(clubMappings);
    } catch {
      // fall through — retry with the raw file anyway
    }
    const source = clubDialog.source;
    const rest = remainingSources;
    remainingSources = [];
    clubDialog = null;
    const sources = rest.length > 0 ? [source, ...rest] : [source];
    await handleSources(sources);
  }

  async function skipUnknown() {
    if (!clubDialog) return;
    const source = clubDialog.source;
    const rest = remainingSources;
    remainingSources = [];
    clubDialog = null;
    uploading = true;
    uploads = [...uploads, { label: labelFor(source), status: "uploading" }];
    try {
      const ev = await uploadSource(source, true);
      const idx = uploads.findIndex((u) => u.label === labelFor(source) && u.status === "uploading");
      if (idx !== -1) {
        uploads[idx] = {
          label: labelFor(source), status: "success", id: ev.id, name: ev.name,
          gymnast_count: ev.gymnast_count, score_count: ev.score_count, club_count: ev.club_count,
        };
        uploads = [...uploads];
      }
    } catch (err) {
      const idx = uploads.findIndex((u) => u.label === labelFor(source) && u.status === "uploading");
      if (idx !== -1) {
        uploads[idx] = { label: labelFor(source), status: "error", errorMessage: String(err) };
        uploads = [...uploads];
      }
    } finally {
      uploading = false;
    }
    if (rest.length > 0) {
      await handleSources(rest);
    }
  }

  function ondrop(e: DragEvent) {
    e.preventDefault();
    if (e.dataTransfer?.files && e.dataTransfer.files.length > 0) {
      handleFiles(e.dataTransfer.files);
    }
  }

  function ondragover(e: DragEvent) {
    e.preventDefault();
  }

  function onfileinput(e: Event) {
    const input = e.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      handleFiles(input.files);
      input.value = "";
    }
  }
</script>

<svelte:head>
  <title>Upload — NZ Gymnastics Results</title>
</svelte:head>

<div class="max-w-6xl mx-auto">
  <h1 class="text-3xl font-bold mb-2">Upload Event</h1>

  <p class="text-base-content/70 mb-6">
    Upload a Scoreholder JSON export to view, export, and analyse results.
  </p>

  {#if authCfg && !loggedIn}
    <div class="card bg-base-200 mt-4">
      <div class="card-body items-center text-center py-12">
        <span class="text-4xl mb-2">🔐</span>
        <p class="text-base-content/70 mb-4">You need to log in to upload events.</p>
        <a href="/login" class="btn btn-primary btn-sm">Log in</a>
      </div>
    </div>
  {:else}
    <div
      class="card border-2 border-dashed border-base-content/30 hover:border-primary bg-base-200/50 hover:bg-base-200 cursor-pointer transition-all p-12 text-center"
      role="button"
      tabindex="0"
      ondrop={ondrop}
      ondragover={ondragover}
    >
      {#if uploading}
        <div class="flex flex-col items-center gap-3">
          <span class="loading loading-spinner loading-lg text-primary"></span>
          <p class="text-base-content/70">Uploading and parsing...</p>
        </div>
      {:else}
        <div class="flex flex-col items-center gap-3">
          <span class="text-4xl">📄</span>
          <p class="text-base-content/70">Drop Scoreholder JSON files here, or click to browse</p>
          <input type="file" accept=".json" multiple onchange={onfileinput} hidden />
        </div>
      {/if}
    </div>

    <div class="divider text-base-content/40">or</div>

    <div class="card bg-base-200/50">
      <div class="card-body p-6">
        <div class="flex flex-col gap-2">
          <label for="scoreholder-url" class="text-sm font-medium">Import from Scoreholder links</label>
          <textarea
            id="scoreholder-url"
            class="textarea textarea-bordered w-full font-mono text-sm"
            rows="3"
            placeholder={"Paste one or more links, one per line\nhttps://scoreholder.com/en/events/..."}
            bind:value={urlInput}
            onkeydown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                e.preventDefault();
                handleUrl();
              }
            }}
          ></textarea>
          <div class="flex items-center gap-2">
            <button class="btn btn-primary" onclick={handleUrl} disabled={!urlInput.trim() || uploading}>
              Import
            </button>
            {#if urlInput.trim()}
              <span class="text-xs text-base-content/50">
                {urlInput.split(/\r?\n/).map((u) => u.trim()).filter((u) => u.length > 0).length} link(s)
              </span>
            {/if}
          </div>
        </div>
      </div>
    </div>

    {#if uploads.length > 0}
      <div class="mt-6 space-y-3">
        {#each uploads as item}
          {#if item.status === "uploading"}
            <div class="card bg-base-200 border border-base-300">
              <div class="card-body p-4 flex-row items-center gap-3">
                <span class="loading loading-spinner loading-sm text-primary"></span>
                <span class="font-medium">{item.label}</span>
                <span class="text-base-content/50 text-sm ml-auto">Uploading...</span>
              </div>
            </div>
          {:else if item.status === "success"}
            <div class="card bg-base-200 border border-success/30">
              <div class="card-body p-4">
                <div class="flex items-center gap-3">
                  <span class="text-success text-xl">&#10003;</span>
                  <span class="font-medium">{item.label}</span>
                  <span class="text-sm text-base-content/50 ml-auto">Imported</span>
                </div>
                <div class="mt-1 text-sm">
                  <strong>{item.name}</strong>
                  <span class="text-base-content/50 mx-2">&middot;</span>
                  <span>{item.gymnast_count} gymnasts</span>
                  {#if item.score_count != null}
                    <span class="text-base-content/50 mx-2">&middot;</span>
                    <span>{item.score_count} scores</span>
                  {/if}
                  {#if item.club_count != null}
                    <span class="text-base-content/50 mx-2">&middot;</span>
                    <span>{item.club_count} clubs</span>
                  {/if}
                  {#if item.names_unified && item.names_unified > 0}
                    <div class="mt-1 text-xs text-base-content/60">
                      {item.ids_corrected} IDs corrected, {item.names_unified} names unified
                      {#if item.conflicts && item.conflicts.length > 0}
                        <span class="text-warning ml-1">
                          ⚠ {item.conflicts.length} conflicts (review in admin dashboard)
                        </span>
                      {/if}
                    </div>
                  {/if}
                </div>
                <div class="card-actions mt-2">
                  <a href="/events/{item.id}" class="btn btn-primary btn-xs">View Results</a>
                </div>
              </div>
            </div>
          {:else if item.status === "error"}
            <div class="alert alert-error">
              <div class="flex flex-col gap-1 w-full">
                <div class="flex items-center gap-2">
                  <span class="text-lg">&#10007;</span>
                  <span class="font-medium">{item.label}</span>
                </div>
                <span class="text-sm">{item.errorMessage}</span>
                {#if item.errorDetails && item.errorDetails.length > 0}
                  <ul class="list-disc list-inside text-xs opacity-80">
                    {#each item.errorDetails as detail}
                      <li>{detail}</li>
                    {/each}
                  </ul>
                {/if}
                {#if item.errorRaw}
                  <details class="mt-1">
                    <summary class="text-xs cursor-pointer opacity-60">Raw error</summary>
                    <pre class="text-xs opacity-60 whitespace-pre-wrap max-h-32 overflow-y-auto bg-base-300 p-2 rounded mt-1">{item.errorRaw}</pre>
                  </details>
                {/if}
              </div>
            </div>
          {/if}
        {/each}
      </div>

      <div class="text-center mt-6">
        <a href="/events" class="btn btn-ghost btn-sm">View all events</a>
      </div>
    {/if}

    <p class="text-center text-base-content/50 mt-8">
      Already uploaded an event? <a href="/events" class="link link-primary">Browse events</a>
    </p>
  {/if}
</div>

{#if clubDialog}
  <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onclick={() => (clubDialog = null)}>
    <div class="bg-base-100 rounded-box shadow-xl p-6 w-full max-w-lg mx-4" onclick={(e) => e.stopPropagation()}>
      <h3 class="text-lg font-bold mb-2">Unknown Club Names</h3>
      <p class="text-sm text-base-content/70 mb-4">
        Some clubs in this file aren't in the known club list.
        Map each to an existing club or skip to keep the original names.
      </p>
      <div class="space-y-3 max-h-80 overflow-y-auto">
        {#each clubDialog.unknown as unknown}
          <div>
            <label class="text-sm font-medium block mb-1">"{unknown}" maps to:</label>
            <select
              class="select select-bordered select-sm w-full"
              value={clubMappings[unknown]}
              onchange={(e) => {
                const target = e.target as HTMLSelectElement;
                clubMappings[unknown] = target.value;
                clubMappings = { ...clubMappings };
              }}
            >
              {#each clubDialog.known as known}
                <option value={known}>{known}</option>
              {/each}
            </select>
          </div>
        {/each}
      </div>
      <div class="flex justify-end gap-2 mt-6">
        <button class="btn btn-ghost btn-sm" onclick={() => (clubDialog = null)}>Cancel</button>
        <button class="btn btn-ghost btn-sm" onclick={skipUnknown}>Skip (keep original)</button>
        <button class="btn btn-primary btn-sm" onclick={saveAndRetry}>Save &amp; Retry</button>
      </div>
    </div>
  </div>
{/if}
