<script lang="ts">
  import { goto } from "$app/navigation";
  import { authLogin } from "$lib/api";
  import { authConfigured, setToken } from "$lib/auth";
  import { onMount } from "svelte";

  let username = $state("");
  let password = $state("");
  let error = $state<string | null>(null);
  let loading = $state(false);
  let configured = $state(true);

  onMount(() => {
    const unsub = authConfigured.subscribe((v) => {
      configured = v;
    });
    return unsub;
  });

  async function handleSubmit() {
    if (!username.trim() || !password.trim()) return;
    loading = true;
    error = null;
    try {
      const data = await authLogin(username.trim(), password.trim());
      setToken(data.access_token);
      goto("/");
    } catch (err) {
      error = String(err);
    } finally {
      loading = false;
    }
  }
</script>

<svelte:head>
  <title>Login — NZ Gymnastics Results</title>
</svelte:head>

<div class="max-w-md mx-auto mt-12">
  <div class="card bg-base-200">
    <div class="card-body">
      <h2 class="card-title text-2xl mb-2">Login</h2>

      {#if !configured}
        <div role="alert" class="alert alert-warning">
          <span>No authentication configured on this server.</span>
        </div>
        <div class="card-actions mt-2">
          <a href="/" class="btn btn-primary btn-sm">Go Home</a>
        </div>
      {:else}
        <div class="flex flex-col gap-4">
          <input
            type="text"
            class="input input-bordered w-full"
            placeholder="Username"
            bind:value={username}
            autofocus
          />
          <input
            type="password"
            class="input input-bordered w-full"
            placeholder="Password"
            bind:value={password}
            onkeydown={(e) => {
              if (e.key === "Enter") handleSubmit();
            }}
          />
          {#if error}
            <div role="alert" class="alert alert-error py-2">
              <span class="text-sm">{error}</span>
            </div>
          {/if}
          <button
            class="btn btn-primary"
            onclick={handleSubmit}
            disabled={loading || !username.trim() || !password.trim()}
          >
            {loading ? "Logging in..." : "Log in"}
          </button>
        </div>
      {/if}
    </div>
  </div>
</div>
