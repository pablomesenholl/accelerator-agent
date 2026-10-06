Project Log

17.09.26: 
	create PROJECT_LOG.md
	initialize git repo for the semester project
	set up ColliderAgent up to Magnus
	set up a generic .gitignore
21.09.26:
	set up a serial build for OPALX
	include unit tests in OPALX
	run a minimal-drift example successfully
	read and work through https://opalx-project.github.io/opalx-manual/getting-started/worked-inputs.html
	start to analyse test sim input and output files
22.09.26:
	analysed minimal-drift example input and output
	small test plotting of statistics
23.09.26:
	FODO no spacecharge working directory
	FODO no spacecharge start on input file
	OPALX MAD style input file template created	
24.09.26: 
	First FODO no spacecharge input file works
	Params for distr for FODO input can be improved
	Learn about accelerator physics and FODO cell
25.09.26:
	Do the math to match momentum width to space width of fodo cell
	Run improved FODO cell
	Create python analysis script to plot: envelopes, emittance, corr and phase space snapshots
26.09.26:
	Inspect plots of 1cell FODO simulations
	Create directories for 10 & 100 fodo periods
28.09.26:
	Plot analytic behaviour of FODO next to OPLAX 
	Adjust input file to work for 10cell fodo case, including a lattice generator
	Postprocess and plot 10cell fodo with analytic behaviour of OPALX initial values
29.09.26:
	Install Docker
	Install other dependencies for magnus
	Install magnus locally and make it work
30.09.26:
	Do a ColliderAgent specific run manually on Magnus for MadGraph-compiler only:
		magnus run madgraph-compile --\
			--model sm\
			--process "pp > e+e-"\
			--output smoke_test/dy
	Found 2 bugs of magnus with WSL and Docker desktop windows setup:
		1. MG5 3.7.0 auto-update shutdown bug
		   → fixed with `set auto_update 0`

		2. WSL + Docker Desktop networking mismatch
		   → fixed with
	    	MAGNUS_ADDRESS=http://host.docker.internal:8017
01.10.26:
	Fork magnus from upstream and create a new branch: fix-wsl-docker-networking
	In that branch fix the WSL and Docker Desktop mismatch on magnus source level
	Networking mismatch fix works and is committed
	Think about adding a regression test, a small documentation, pushing and creating an issue for magnus
	Inspect ColliderAgent skills
	Create a beta Skills architecture for accelerator-agent based on ColliderAgent skills		
5.10.26:
	Activate Wolfram licence for ColliderAgent
	Fix MadGraph specific bugs (there were 2) in ColliderAgent in separate fork
	New way to launch Magnus local (scripts/setup_magnus.py) such that local branch with updated blueprints are used
	Do the pp -> l+l- test of ColliderAgent using Codex with updated ColliderAgent fork
	Test worked: 50000 events and dilepton invariant mass plot and pdf
