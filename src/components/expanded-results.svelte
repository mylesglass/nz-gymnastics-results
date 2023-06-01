<script>
    import AppScoreDetails from '../components/app-score-details.svelte'

    export let row;
</script>

<div class="grid grid-cols-3 gap-4 shadow bg-primary text-primary-content">
	<div class="stat">
		<p>{ row['name'] }</p>
		<p>Gymnastics Club Inc</p>
		<p>Competition Name</p>
		<p>Competition Date</p>
		<p>Type of Round</p>
	</div>

	<div class="grid grid-cols-2">
		<AppScoreDetails
            event="Vault"
            score="13.900"
            dscore="3.4"
            rank="1"
            field-size="22"
        />
	</div>

	<div class="stat">
		<div class="stat-figure text-primary">
			<span class="text-5xl">🥇</span>
		</div>
		<div class="stat-title">All Around Score</div>
		<div class="stat-value">55.000</div>
		<div class="stat-desc">1st out of 22</div>
	</div>
</div>
