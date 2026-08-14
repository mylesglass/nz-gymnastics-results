<script lang="ts">
  import { onMount } from "svelte";
  import { getToken, PERMISSIONS } from "$lib/auth";
  import { updateUserPermissions } from "$lib/api";
  import Dialog from "$lib/Dialog.svelte";

  interface User {
    id: number;
    username: string;
    role: string;
    permissions: string[];
    created_at: string;
  }

  const PERMISSION_OPTIONS = [
    { key: PERMISSIONS.national, label: "National Rankings" },
    { key: PERMISSIONS.wellington, label: "Wellington Rankings" },
  ];

  let users = $state<User[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let currentUsername = $state("");

  // Add user modal
  let showAdd = $state(false);
  let newUsername = $state("");
  let newPassword = $state("");
  let newRole = $state("member");
  let newPerms = $state<string[]>([PERMISSIONS.national]);
  let adding = $state(false);
  let addError = $state<string | null>(null);

  // Reset password modal
  let resetTarget = $state<User | null>(null);
  let resetPassword = $state("");
  let resetting = $state(false);
  let resetError = $state<string | null>(null);

  // Delete confirmation
  let deleteTarget = $state<User | null>(null);
  let deleting = $state(false);

  // Permission edits
  let permDrafts = $state<Record<number, string[]>>({});
  let permChanged = $state<Record<number, boolean>>({});
  let permError = $state<Record<number, string>>({});
  let savingPermId = $state<number | null>(null);
  let permToast = $state<string | null>(null);
  let permToastTimer: ReturnType<typeof setTimeout> | undefined;

  function headers() {
    const t = getToken();
    return t ? { Authorization: `Bearer ${t}`, "Content-Type": "application/json" } : { "Content-Type": "application/json" };
  }

  async function loadUsers() {
    loading = true;
    error = null;
    try {
      const res = await fetch("/api/auth/users", { headers: headers() });
      if (!res.ok) throw new Error(await res.text());
      users = await res.json();
      for (const u of users) {
        permDrafts[u.id] = [...u.permissions];
        permChanged[u.id] = false;
        permError[u.id] = "";
      }
    } catch (e) {
      error = String(e);
    } finally {
      loading = false;
    }
  }

  function getCurrentUsername(): string {
    const t = getToken();
    if (!t) return "";
    try {
      const payload = JSON.parse(atob(t.split(".")[1]));
      return payload.sub || "";
    } catch {
      return "";
    }
  }

  onMount(() => {
    currentUsername = getCurrentUsername();
    loadUsers();
  });

  function togglePerm(userId: number, key: string) {
    const cur = permDrafts[userId] ?? [];
    permDrafts[userId] = cur.includes(key) ? cur.filter((p) => p !== key) : [...cur, key];
    permChanged[userId] = true;
    permError[userId] = "";
  }

  function toggleNewPerm(key: string) {
    newPerms = newPerms.includes(key) ? newPerms.filter((p) => p !== key) : [...newPerms, key];
  }

  async function savePerms(u: User) {
    savingPermId = u.id;
    permError[u.id] = "";
    clearTimeout(permToastTimer);
    try {
      const res = await updateUserPermissions(u.id, permDrafts[u.id] ?? []);
      u.permissions = [...res.permissions];
      permDrafts[u.id] = [...res.permissions];
      permChanged[u.id] = false;
      permToast = `Permissions updated for ${u.username}`;
    } catch (e) {
      permError[u.id] = String(e);
    } finally {
      savingPermId = null;
    }
    permToastTimer = setTimeout(() => { permToast = null; }, 4000);
  }

  async function submitAdd() {
    if (!newUsername.trim() || !newPassword.trim()) return;
    adding = true;
    addError = null;
    try {
      const res = await fetch("/api/auth/register", {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({
          username: newUsername.trim(),
          password: newPassword.trim(),
          role: newRole,
          permissions: newRole === "admin" ? [] : newPerms,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      showAdd = false;
      newUsername = "";
      newPassword = "";
      newRole = "member";
      newPerms = [PERMISSIONS.national];
      await loadUsers();
    } catch (e) {
      addError = String(e);
    } finally {
      adding = false;
    }
  }

  async function submitReset() {
    if (!resetTarget || !resetPassword.trim()) return;
    resetting = true;
    resetError = null;
    try {
      const res = await fetch(`/api/auth/users/${resetTarget.id}/reset-password`, {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({ password: resetPassword.trim() }),
      });
      if (!res.ok) throw new Error(await res.text());
      resetTarget = null;
      resetPassword = "";
    } catch (e) {
      resetError = String(e);
    } finally {
      resetting = false;
    }
  }

  async function confirmDelete() {
    if (!deleteTarget) return;
    deleting = true;
    try {
      const res = await fetch(`/api/auth/users/${deleteTarget.id}`, {
        method: "DELETE",
        headers: headers(),
      });
      if (!res.ok) throw new Error(await res.text());
      deleteTarget = null;
      await loadUsers();
    } catch (e) {
      error = String(e);
    } finally {
      deleting = false;
    }
  }

  function roleBadge(role: string) {
    if (role === "admin") return "badge badge-primary badge-sm";
    return "badge badge-ghost badge-sm";
  }
</script>

<div class="flex items-center justify-between mb-4">
  <p class="text-sm text-base-content/70">Manage accounts and permissions</p>
  <button class="btn btn-primary btn-sm" onclick={() => (showAdd = true)}>
    Add User
  </button>
</div>

{#if loading}
  <div class="flex justify-center py-12">
    <span class="loading loading-spinner loading-lg text-primary"></span>
  </div>
{:else if error}
  <div role="alert" class="alert alert-error">
    <span>{error}</span>
  </div>
{:else}
  <div class="overflow-x-auto">
    <table class="table table-zebra">
      <thead>
        <tr>
          <th scope="col">Username</th>
          <th scope="col">Role</th>
          <th scope="col">Permissions</th>
          <th scope="col">Created</th>
          <th scope="col" class="w-40">Actions</th>
        </tr>
      </thead>
      <tbody>
        {#each users as u}
          <tr>
            <td class="font-medium">
              {u.username}
              {#if u.username === currentUsername}
                <span class="text-xs text-base-content/70 ml-1">(you)</span>
              {/if}
            </td>
            <td><span class={roleBadge(u.role)}>{u.role}</span></td>
            <td>
              {#if u.role === "admin"}
                <span class="text-xs text-base-content/70">Full access</span>
              {:else}
                <div class="flex flex-wrap items-center gap-x-4 gap-y-1">
                  {#each PERMISSION_OPTIONS as opt}
                    <label class="flex items-center gap-1.5 cursor-pointer">
                      <input
                        type="checkbox"
                        class="checkbox checkbox-xs"
                        checked={(permDrafts[u.id] ?? []).includes(opt.key)}
                        onchange={() => togglePerm(u.id, opt.key)}
                      />
                      <span class="text-sm">{opt.label}</span>
                    </label>
                  {/each}
                  {#if permChanged[u.id]}
                    <button
                      class="btn btn-primary btn-xs"
                      disabled={savingPermId === u.id}
                      onclick={() => savePerms(u)}
                    >
                      {savingPermId === u.id ? "Saving..." : "Save"}
                    </button>
                  {/if}
                  {#if permError[u.id]}
                    <span class="text-xs text-error">{permError[u.id]}</span>
                  {/if}
                </div>
              {/if}
            </td>
            <td class="text-sm text-base-content/70">{new Date(u.created_at).toLocaleDateString()}</td>
            <td>
              <div class="flex gap-1">
                <button
                  class="btn btn-ghost btn-xs"
                  aria-label={`Reset password for ${u.username}`}
                  onclick={() => { resetTarget = u; resetPassword = ""; resetError = null; }}
                >
                  <span aria-hidden="true">🔑</span>
                </button>
                {#if u.username !== currentUsername}
                  <button
                    class="btn btn-ghost btn-xs text-error"
                    aria-label={`Delete user ${u.username}`}
                    onclick={() => { deleteTarget = u; }}
                  >
                    <span aria-hidden="true">🗑️</span>
                  </button>
                {/if}
              </div>
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}

<!-- Add User Modal -->
{#if showAdd}
  <Dialog title="Add User" onClose={() => (showAdd = false)}>
    <div class="flex flex-col gap-3">
      <label for="add-username" class="sr-only">Username</label>
      <input
        id="add-username"
        type="text"
        class="input input-bordered w-full"
        placeholder="Username"
        bind:value={newUsername}
      />
      <label for="add-password" class="sr-only">Password</label>
      <input
        id="add-password"
        type="password"
        class="input input-bordered w-full"
        placeholder="Password"
        bind:value={newPassword}
      />
      <label for="add-role" class="sr-only">Role</label>
      <select id="add-role" class="select select-bordered w-full" bind:value={newRole}>
        <option value="member">Member</option>
        <option value="admin">Admin</option>
      </select>
      {#if newRole === "member"}
        <fieldset>
          <legend class="text-sm text-base-content/70 mb-1">Page access</legend>
          <div class="flex flex-col gap-1">
            {#each PERMISSION_OPTIONS as opt}
              <label class="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  class="checkbox checkbox-xs"
                  checked={newPerms.includes(opt.key)}
                  onchange={() => toggleNewPerm(opt.key)}
                />
                <span class="text-sm">{opt.label}</span>
              </label>
            {/each}
          </div>
        </fieldset>
      {:else}
        <p class="text-xs text-base-content/70">Admins always have full access to all pages.</p>
      {/if}
      {#if addError}
        <div role="alert" class="alert alert-error py-2">
          <span class="text-sm">{addError}</span>
        </div>
      {/if}
    </div>
    <div class="flex justify-end gap-2 mt-4">
      <button class="btn btn-ghost btn-sm" onclick={() => (showAdd = false)}>Cancel</button>
      <button
        class="btn btn-primary btn-sm"
        onclick={submitAdd}
        disabled={adding || !newUsername.trim() || !newPassword.trim()}
      >
        {adding ? "Adding..." : "Add User"}
      </button>
    </div>
  </Dialog>
{/if}

<!-- Reset Password Modal -->
{#if resetTarget}
  <Dialog title="Reset Password" onClose={() => (resetTarget = null)}>
    <p class="text-sm text-base-content/70 mb-4">
      New password for <strong>{resetTarget.username}</strong>
    </p>
    <label for="reset-password" class="sr-only">New password</label>
    <input
      id="reset-password"
      type="password"
      class="input input-bordered w-full"
      placeholder="New password"
      bind:value={resetPassword}
    />
    {#if resetError}
      <div role="alert" class="alert alert-error py-2 mt-2">
        <span class="text-sm">{resetError}</span>
      </div>
    {/if}
    <div class="flex justify-end gap-2 mt-4">
      <button class="btn btn-ghost btn-sm" onclick={() => (resetTarget = null)}>Cancel</button>
      <button
        class="btn btn-primary btn-sm"
        onclick={submitReset}
        disabled={resetting || !resetPassword.trim()}
      >
        {resetting ? "Resetting..." : "Reset Password"}
      </button>
    </div>
  </Dialog>
{/if}

<!-- Delete Confirmation Modal -->
{#if deleteTarget}
  <Dialog title="Delete User" onClose={() => (deleteTarget = null)}>
    <p class="text-base-content/70">
      Are you sure you want to delete <strong>"{deleteTarget.username}"</strong>?
      This cannot be undone.
    </p>
    <div class="flex justify-end gap-2 mt-4">
      <button class="btn btn-ghost btn-sm" onclick={() => (deleteTarget = null)}>Cancel</button>
      <button
        class="btn btn-error btn-sm"
        onclick={confirmDelete}
        disabled={deleting}
      >
        {deleting ? "Deleting..." : "Delete"}
      </button>
    </div>
  </Dialog>
{/if}

{#if permToast}
  <div class="toast toast-bottom toast-end z-50" role="status">
    <div class="alert alert-success text-sm">
      <span>{permToast}</span>
    </div>
  </div>
{/if}
