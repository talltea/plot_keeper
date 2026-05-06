<script lang="ts">
  import { onMount } from "svelte";
  import { ping, type Ping } from "./lib/api";

  let result = $state<Ping | null>(null);
  let error = $state<string | null>(null);

  onMount(async () => {
    try {
      result = await ping();
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
  });

  const today = new Date();
  const weekday = today.toLocaleDateString("en-GB", { weekday: "long" });
  const dateStr = today.toLocaleDateString("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
</script>

<main class="phone">
  <header class="mast">
    <h1 class="title">The <em>Garden</em> Book</h1>
    <div class="date">
      {weekday} <span class="gilt">❦</span> <b>{dateStr}</b>
    </div>
  </header>

  <h2>
    Phase 0
    <span class="sub">scaffold smoke</span>
  </h2>

  <section class="ping">
    {#if error}
      <p class="err">Server unreachable: {error}</p>
    {:else if result}
      <p>
        Server is up. Schema version <b>{result.schema_version}</b>
        as of <i>{result.now}</i>.
      </p>
    {:else}
      <p class="dim">Awaiting server reply…</p>
    {/if}
  </section>
</main>

<style>
  .ping {
    text-align: center;
    padding: 18px 8px;
    border-top: 1px solid var(--rule);
    border-bottom: 1px solid var(--rule);
    background: rgba(255, 255, 255, 0.18);
  }
  .ping p {
    margin: 0;
    font-size: 15px;
    color: var(--ink-2);
    font-style: italic;
  }
  .ping b {
    font-style: normal;
    color: var(--ink);
  }
  .ping .err {
    color: var(--rust);
  }
  .ping .dim {
    color: var(--ink-3);
  }
</style>
