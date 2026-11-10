<svelte:head>
	<title>FlakeGuard</title>
	<meta name="description" content="CI reliability intelligence for GitHub Actions." />
</svelte:head>

<main>
	<p class="eyebrow">CI reliability intelligence</p>
	<h1>FlakeGuard</h1>
	<p class="intro">A foundation for understanding test reliability across GitHub Actions runs.</p>
	<p class="status">Development foundation ready</p>
</main>

<style>
	:global(body) {
		margin: 0;
		background: #f5f7f6;
		color: #18312b;
		font-family: Inter, ui-sans-serif, system-ui, sans-serif;
	}
	main {
		box-sizing: border-box;
		max-width: 720px;
		margin: 14vh auto;
		padding: 48px;
		border: 1px solid #d9e3df;
		border-radius: 18px;
		background: #fff;
		box-shadow: 0 18px 50px #18312b0b;
	}
	.eyebrow {
		color: #19745c;
		font-size: 0.8rem;
		font-weight: 700;
		letter-spacing: 0.12em;
		text-transform: uppercase;
	}
	h1 {
		margin: 12px 0;
		font-size: clamp(2.5rem, 8vw, 4rem);
		letter-spacing: -0.06em;
	}
	.intro {
		max-width: 520px;
		color: #52645f;
		font-size: 1.15rem;
		line-height: 1.6;
	}
	.status {
		display: inline-block;
		margin-top: 24px;
		padding: 9px 13px;
		border-radius: 999px;
		background: #e5f5ee;
		color: #176246;
		font-size: 0.9rem;
	}
	@media (max-width: 600px) {
		main { margin: 8vh 16px; padding: 28px; }
	}
</style>
