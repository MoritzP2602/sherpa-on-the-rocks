#include "V.H"

using namespace AMEGIC;
using namespace ATOOLS;
using namespace std;

extern "C" Values* Getter_V2_3__d__u__G__d__u__O3_0(Basic_Sfuncs* bs) {
  return new V2_3__d__u__G__d__u__O3_0(bs);
}

V2_3__d__u__G__d__u__O3_0::V2_3__d__u__G__d__u__O3_0(Basic_Sfuncs* _BS) :
     Basic_Func(0,_BS),
     Basic_Zfunc(0,_BS),
     Basic_Xfunc(0,_BS),
     Basic_Vfunc(0,_BS),
     Basic_Pfunc(0,_BS)
{
  f = new int[3];
  c = new Complex[4];
  Z = new Complex[121];
  M = new Complex*[32];
  for(int i=0;i<32;i++) M[i] = new Complex[5];
  cl = new int[32];
}

V2_3__d__u__G__d__u__O3_0::~V2_3__d__u__G__d__u__O3_0()
{
  if (Z)  delete[] Z;
  if (f)  delete[] f;
  if (c)  delete[] c;
  if (cl) delete[] cl;
  if (M) {
    for(int i=0;i<32;i++) delete[] M[i];
    delete[] M;
  }
}

Complex V2_3__d__u__G__d__u__O3_0::Evaluate(int m,int n)
{
  if (cl[n]) return M[n][m];
  switch (n) {
    case 0: Calculate_M0(); break;
    case 1: Calculate_M1(); break;
    case 2: Calculate_M2(); break;
    case 3: Calculate_M3(); break;
    case 4: Calculate_M4(); break;
    case 5: Calculate_M5(); break;
    case 6: Calculate_M6(); break;
    case 7: Calculate_M7(); break;
    case 8: Calculate_M8(); break;
    case 9: Calculate_M9(); break;
    case 10: Calculate_M10(); break;
    case 11: Calculate_M11(); break;
    case 12: Calculate_M12(); break;
    case 13: Calculate_M13(); break;
    case 14: Calculate_M14(); break;
    case 15: Calculate_M15(); break;
    case 16: Calculate_M16(); break;
    case 17: Calculate_M17(); break;
    case 18: Calculate_M18(); break;
    case 19: Calculate_M19(); break;
    case 20: Calculate_M20(); break;
    case 21: Calculate_M21(); break;
    case 22: Calculate_M22(); break;
    case 23: Calculate_M23(); break;
    case 24: Calculate_M24(); break;
    case 25: Calculate_M25(); break;
    case 26: Calculate_M26(); break;
    case 27: Calculate_M27(); break;
    case 28: Calculate_M28(); break;
    case 29: Calculate_M29(); break;
    case 30: Calculate_M30(); break;
    case 31: Calculate_M31(); break;
  }
  cl[n]=1;
  return M[n][m];
}

void V2_3__d__u__G__d__u__O3_0::Calculate_M0()
{
  M[0][0] = -Z[7]*Z[4]*Z[3];
  M[0][1] = (Z[10]*Z[9]-Z[4]*Z[8])*Z[12];
  M[0][2] = -Z[20]*Z[4]*Z[16];
  M[0][3] = (Z[24]*Z[23]-Z[21]*Z[4])*Z[27];
  M[0][4] = -Z[37]*Z[38];
}

void V2_3__d__u__G__d__u__O3_0::Calculate_M1()
{
  M[1][0] = -Z[7]*Z[22]*Z[3];
  M[1][1] = (Z[40]*Z[9]-Z[22]*Z[8])*Z[12];
  M[1][2] = -Z[20]*Z[22]*Z[16];
  M[1][3] = (Z[44]*Z[23]-Z[21]*Z[22])*Z[27];
  M[1][4] = -Z[49]*Z[38];
}

void V2_3__d__u__G__d__u__O3_0::Calculate_M2()
{
}

void V2_3__d__u__G__d__u__O3_0::Calculate_M3()
{
}

void V2_3__d__u__G__d__u__O3_0::Calculate_M4()
{
  M[4][0] = -(Z[2]*Z[55]+Z[4]*Z[56])*Z[7];
  M[4][1] = -Z[12]*Z[4]*Z[57];
  M[4][2] = -(Z[14]*Z[59]+Z[4]*Z[60])*Z[20];
  M[4][3] = -Z[27]*Z[61]*Z[4];
  M[4][4] = -Z[68]*Z[38];
}

void V2_3__d__u__G__d__u__O3_0::Calculate_M5()
{
  M[5][0] = -(Z[39]*Z[55]+Z[22]*Z[56])*Z[7];
  M[5][1] = -Z[12]*Z[22]*Z[57];
  M[5][2] = -(Z[41]*Z[59]+Z[22]*Z[60])*Z[20];
  M[5][3] = -Z[27]*Z[61]*Z[22];
  M[5][4] = -Z[72]*Z[38];
}

void V2_3__d__u__G__d__u__O3_0::Calculate_M6()
{
}

void V2_3__d__u__G__d__u__O3_0::Calculate_M7()
{
}

void V2_3__d__u__G__d__u__O3_0::Calculate_M8()
{
  M[8][0] = -Z[7]*Z[17]*Z[3];
  M[8][1] = (Z[75]*Z[9]-Z[17]*Z[8])*Z[12];
  M[8][2] = -(Z[15]*Z[76]+Z[17]*Z[16])*Z[20];
  M[8][3] = -Z[27]*Z[21]*Z[17];
  M[8][4] = -Z[81]*Z[38];
}

void V2_3__d__u__G__d__u__O3_0::Calculate_M9()
{
  M[9][0] = -Z[7]*Z[43]*Z[3];
  M[9][1] = (Z[83]*Z[9]-Z[43]*Z[8])*Z[12];
  M[9][2] = -(Z[42]*Z[76]+Z[43]*Z[16])*Z[20];
  M[9][3] = -Z[27]*Z[21]*Z[43];
  M[9][4] = -Z[87]*Z[38];
}

void V2_3__d__u__G__d__u__O3_0::Calculate_M10()
{
}

void V2_3__d__u__G__d__u__O3_0::Calculate_M11()
{
}

void V2_3__d__u__G__d__u__O3_0::Calculate_M12()
{
  M[12][0] = -(Z[74]*Z[55]+Z[17]*Z[56])*Z[7];
  M[12][1] = -Z[12]*Z[17]*Z[57];
  M[12][2] = -Z[20]*Z[17]*Z[60];
  M[12][3] = (Z[63]*Z[77]-Z[61]*Z[17])*Z[27];
  M[12][4] = -Z[94]*Z[38];
}

void V2_3__d__u__G__d__u__O3_0::Calculate_M13()
{
  M[13][0] = -(Z[82]*Z[55]+Z[43]*Z[56])*Z[7];
  M[13][1] = -Z[12]*Z[43]*Z[57];
  M[13][2] = -Z[20]*Z[43]*Z[60];
  M[13][3] = (Z[70]*Z[77]-Z[61]*Z[43])*Z[27];
  M[13][4] = -Z[96]*Z[38];
}

void V2_3__d__u__G__d__u__O3_0::Calculate_M14()
{
}

void V2_3__d__u__G__d__u__O3_0::Calculate_M15()
{
}

void V2_3__d__u__G__d__u__O3_0::Calculate_M16()
{
}

void V2_3__d__u__G__d__u__O3_0::Calculate_M17()
{
}

void V2_3__d__u__G__d__u__O3_0::Calculate_M18()
{
  M[18][0] = -(Z[50]*Z[97]+Z[51]*Z[3])*Z[7];
  M[18][1] = -Z[12]*Z[51]*Z[8];
  M[18][2] = -Z[20]*Z[51]*Z[16];
  M[18][3] = (Z[24]*Z[102]-Z[21]*Z[51])*Z[27];
  M[18][4] = -Z[106]*Z[38];
}

void V2_3__d__u__G__d__u__O3_0::Calculate_M19()
{
  M[19][0] = -(Z[53]*Z[97]+Z[54]*Z[3])*Z[7];
  M[19][1] = -Z[12]*Z[54]*Z[8];
  M[19][2] = -Z[20]*Z[54]*Z[16];
  M[19][3] = (Z[44]*Z[102]-Z[21]*Z[54])*Z[27];
  M[19][4] = -Z[109]*Z[38];
}

