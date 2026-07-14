<script lang="ts">
  import { onMount } from "svelte";
  import { uploadFile, checkAuthStatus } from "$lib/api";
  import { isLoggedIn, authConfigured } from "$lib/auth";

  interface UploadItem {
    file: string;
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

  onMount(() => {
    checkAuthStatus()
      .then((s) => authConfigured.set(s.configured))
      .catch(() => {});
    const unsub1 = isLoggedIn.subscribe((v) => (loggedIn = v));
    const unsub2 = authConfigured.subscribe((v) => (authCfg = v));
    return () => {
      unsub1();
      unsub2();
    };
  });

  async function handleFiles(fileList: FileList | File[]) {
    const files = Array.from(fileList).filter((f) => f.name.endsWith(".json"));
    if (files.length === 0) return;

    uploading = true;
    uploads = [];

    for (const file of files) {
      uploads = [...uploads, { file: file.name, status: "uploading" }];

      try {
        const ev = await uploadFile(file);
        const idx = uploads.findIndex((u) => u.file === file.name && u.status === "uploading");
        if (idx !== -1) {
          uploads[idx] = {
            file: file.name,
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
        const idx = uploads.findIndex((u) => u.file === file.name && u.status === "uploading");
        if (idx !== -1) {
          uploads[idx] = {
            file: file.name,
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

    {#if uploads.length > 0}
      <div class="mt-6 space-y-3">
        {#each uploads as item}
          {#if item.status === "uploading"}
            <div class="card bg-base-200 border border-base-300">
              <div class="card-body p-4 flex-row items-center gap-3">
                <span class="loading loading-spinner loading-sm text-primary"></span>
                <span class="font-medium">{item.file}</span>
                <span class="text-base-content/50 text-sm ml-auto">Uploading...</span>
              </div>
            </div>
          {:else if item.status === "success"}
            <div class="card bg-base-200 border border-success/30">
              <div class="card-body p-4">
                <div class="flex items-center gap-3">
                  <span class="text-success text-xl">&#10003;</span>
                  <span class="font-medium">{item.file}</span>
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
                  <span class="font-medium">{item.file}</span>
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
