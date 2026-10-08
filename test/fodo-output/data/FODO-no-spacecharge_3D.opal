OPTION, PSDUMPFREQ=100;
OPTION, STATDUMPFREQ=1;
OPTION, AUTOPHASE=0;
OPTION, VERSION=10900;

TITLE, STRING="FODO cell with no spacecharge";

REAL n_particles=10000;
		REAL bunch_charge=1e-9;
		
REAL Edes=0.250;
		REAL gamma=(Edes+PMASS)/PMASS;
REAL beta=sqrt(1.0-1.0/(gamma*gamma));
REAL P0=gamma*beta*PMASS;
REAL beta_gamma0=beta*gamma;
	
VALUE, {Edes, gamma, beta, P0, beta_gamma0};

REAL LQ = 0.5;
			REAL LD = 0.5;
			REAL k1 = 1.5;
			
REAL Lcell = 2.0*(LQ+LD);
	
REAL sigma_x = 1e-3;
		REAL sigma_y = 1e-3;
REAL sigma_z = 5e-3;
		
REAL kq=sqrt(k1);
REAL phi=kq*LQ;

REAL cq=COS(phi);
REAL sq=SIN(phi);

REAL exp_phi=EXP(phi);
REAL exp_mphi=EXP(-phi);
REAL chq=0.5*(exp_phi+exp_mphi);
REAL shq=0.5*(exp_phi-exp_mphi);
	
REAL qf11=cq;
REAL qf12=sq/kq;
REAL qf21=-kq*sq;
REAL qf22=cq;

REAL qd11=chq;
REAL qd12=shq/kq;
REAL qd21=kq*shq;
REAL qd22=chq;

REAL ax11=qf11 + LD*qf21;
REAL ax12=qf12 + LD*qf22;
REAL ax21=qf21;
REAL ax22=qf22;

REAL bx11=qd11*ax11 + qd12*ax21;
REAL bx12=qd11*ax12 + qd12*ax22;
REAL bx21=qd21*ax11 + qd22*ax21;
REAL bx22=qd21*ax12 + qd22*ax22;

REAL mx11=bx11 + LD*bx21;
REAL mx12=bx12 + LD*bx22;
REAL mx21=bx21;
REAL mx22=bx22;

REAL ay11=qd11 + LD*qd21;
REAL ay12=qd12 + LD*qd22;
REAL ay21=qd21;
REAL ay22=qd22;

REAL by11=qf11*ay11 + qf12*ay21;
REAL by12=qf11*ay12 + qf12*ay22;
REAL by21=qf21*ay11 + qf22*ay21;
REAL by22=qf21*ay12 + qf22*ay22;

REAL my11=by11 + LD*by21;
REAL my12=by12 + LD*by22;
REAL my21=by21;
REAL my22=by22;

REAL cos_mux=0.5*(mx11+mx22);
REAL sin_mux=sqrt(1.0-cos_mux*cos_mux);
REAL mu_x=acos(cos_mux);

REAL twiss_bx=mx12/sin_mux;
REAL twiss_ax=(mx11-mx22)/(2.0*sin_mux);
REAL twiss_gx=-mx21/sin_mux;

REAL cos_muy=0.5*(my11+my22);
REAL sin_muy=sqrt(1.0-cos_muy*cos_muy);
REAL mu_y=acos(cos_muy);

REAL twiss_by=my12/sin_muy;
REAL twiss_ay=(my11-my22)/(2.0*sin_muy);
REAL twiss_gy=-my21/sin_muy;

REAL emit_x=sigma_x*sigma_x/twiss_bx;
REAL emit_y=sigma_y*sigma_y/twiss_by;

REAL sigma_xprime=sigma_x*sqrt(twiss_gx/twiss_bx);
REAL sigma_yprime=sigma_y*sqrt(twiss_gy/twiss_by);

REAL sigma_px=beta_gamma0*sigma_xprime;
REAL sigma_py=beta_gamma0*sigma_yprime;

REAL corr_x=    -twiss_ax/sqrt(twiss_bx*twiss_gx);
REAL corr_y=    -twiss_ay/sqrt(twiss_by*twiss_gy);

VALUE, {    mu_x, mu_y,    twiss_bx, twiss_ax, twiss_gx,    twiss_by, twiss_ay, twiss_gy,    emit_x, emit_y,    sigma_xprime, sigma_yprime,    sigma_px, sigma_py,    corr_x, corr_y};

\1\2 K1=k1;
\1Z = 0.5\2
\1Z = 1.0\2 K1=-k1;
\1Z = 1.5\2

FODOcell: LINE=(QF, D1, QD, D2);

FSNone: FIELDSOLVER, TYPE=NONE,    NX=8, NY=8, NZ=8,    PARFFTX=TRUE, PARFFTY=TRUE, PARFFTZ=TRUE,    BCFFTX=OPEN, BCFFTY=OPEN, BCFFTZ=OPEN;

REAL sigma_pz=1e-5;
		
Dist:	DISTRIBUTION, TYPE=MULTIVARIATEGAUSS,	NPARTDIST=n_particles,
	SIGMAX=sigma_x,	SIGMAY=sigma_y, 	SIGMAZ=sigma_z,			SIGMAPX=sigma_px, 	SIGMAPY=sigma_py,		SIGMAPZ=sigma_pz,	
	CORR={        corr_x,        0.0, 0.0, 0.0, 0.0,        0.0, 0.0, 0.0, 0.0,        corr_y,        0.0, 0.0, 0.0, 0.0, 0.0    };
				
Source: EMISSIONSOURCE, DISTRIBUTION=Dist;
Sources: EMISSIONSOURCELIST=(Source);

Beam1: BEAM, PARTICLE=PROTON,    PC=P0, NALLOC=n_particles,    BCHARGE=bunch_charge, CHARGE=1,    SOURCES=Sources;

TRACK, LINE=FODOcell, BEAM=Beam1,    DT={1e-11}, MAXSTEPS={2000}, ZSTOP={Lcell};
  RUN, METHOD=PARALLEL, FIELDSOLVER=FSNone;
ENDTRACK;

QUIT;


