#include "V.H"

using namespace AMEGIC;
using namespace ATOOLS;
using namespace std;

extern "C" Values* Getter_V2_3__d__db__G__d__db__O3_0(Basic_Sfuncs* bs) {
  return new V2_3__d__db__G__d__db__O3_0(bs);
}

V2_3__d__db__G__d__db__O3_0::V2_3__d__db__G__d__db__O3_0(Basic_Sfuncs* _BS) :
     Basic_Func(0,_BS),
     Basic_Zfunc(0,_BS),
     Basic_Xfunc(0,_BS),
     Basic_Vfunc(0,_BS),
     Basic_Pfunc(0,_BS)
{
  f = new int[2];
  c = new Complex[4];
  Z = new Complex[208];
  M = new Complex*[32];
  for(int i=0;i<32;i++) M[i] = new Complex[10];
  cl = new int[32];
}

V2_3__d__db__G__d__db__O3_0::~V2_3__d__db__G__d__db__O3_0()
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

Complex V2_3__d__db__G__d__db__O3_0::Evaluate(int m,int n)
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

void V2_3__d__db__G__d__db__O3_0::Calculate_M0()
{
  M[0][0] = -(Z[5]*Z[4]-Z[2]*Z[1])*Z[9];
  M[0][1] = Z[19]*Z[21];
  M[0][2] = (Z[5]*Z[24]-Z[2]*Z[22])*Z[26];
  M[0][3] = -Z[35]*Z[37];
  M[0][4] = Z[44]*Z[1]*Z[41];
  M[0][5] = -Z[49]*Z[1]*Z[47];
  M[0][6] = -(Z[1]*Z[50]+Z[52]*Z[51])*Z[54];
  M[0][7] = -Z[56]*Z[22]*Z[41];
  M[0][8] = (Z[22]*Z[50]+Z[57]*Z[51])*Z[58];
  M[0][9] = Z[62]*Z[22]*Z[47];
}

void V2_3__d__db__G__d__db__O3_0::Calculate_M1()
{
  M[1][0] = -(Z[63]*Z[4]-Z[2]*Z[3])*Z[9];
  M[1][1] = Z[68]*Z[21];
  M[1][2] = (Z[63]*Z[24]-Z[2]*Z[23])*Z[26];
  M[1][3] = -Z[72]*Z[37];
  M[1][4] = Z[44]*Z[3]*Z[41];
  M[1][5] = -Z[49]*Z[3]*Z[47];
  M[1][6] = -(Z[3]*Z[50]+Z[77]*Z[51])*Z[54];
  M[1][7] = -Z[56]*Z[23]*Z[41];
  M[1][8] = (Z[23]*Z[50]+Z[79]*Z[51])*Z[58];
  M[1][9] = Z[62]*Z[23]*Z[47];
}

void V2_3__d__db__G__d__db__O3_0::Calculate_M2()
{
  M[2][2] = -Z[26]*Z[2]*Z[61];
  M[2][3] = -Z[87]*Z[37];
  M[2][7] = -Z[56]*Z[61]*Z[41];
  M[2][8] = (Z[61]*Z[50]+Z[92]*Z[51])*Z[58];
  M[2][9] = -(Z[60]*Z[88]-Z[61]*Z[47])*Z[62];
}

void V2_3__d__db__G__d__db__O3_0::Calculate_M3()
{
  M[3][2] = -Z[26]*Z[2]*Z[82];
  M[3][3] = -Z[96]*Z[37];
  M[3][7] = -Z[56]*Z[82]*Z[41];
  M[3][8] = (Z[82]*Z[50]+Z[100]*Z[51])*Z[58];
  M[3][9] = -(Z[81]*Z[88]-Z[82]*Z[47])*Z[62];
}

void V2_3__d__db__G__d__db__O3_0::Calculate_M4()
{
  M[4][0] = Z[9]*Z[101]*Z[1];
  M[4][1] = Z[108]*Z[21];
  M[4][2] = -Z[26]*Z[101]*Z[22];
  M[4][3] = -Z[113]*Z[37];
  M[4][4] = (Z[39]*Z[114]+Z[1]*Z[115])*Z[44];
  M[4][5] = (Z[46]*Z[116]-Z[1]*Z[117])*Z[49];
  M[4][6] = -Z[54]*Z[1]*Z[118];
  M[4][7] = -(Z[55]*Z[114]+Z[22]*Z[115])*Z[56];
  M[4][8] = Z[58]*Z[22]*Z[118];
  M[4][9] = -(Z[59]*Z[116]-Z[22]*Z[117])*Z[62];
}

void V2_3__d__db__G__d__db__O3_0::Calculate_M5()
{
  M[5][0] = Z[9]*Z[101]*Z[3];
  M[5][1] = Z[123]*Z[21];
  M[5][2] = -Z[26]*Z[101]*Z[23];
  M[5][3] = -Z[125]*Z[37];
  M[5][4] = (Z[73]*Z[114]+Z[3]*Z[115])*Z[44];
  M[5][5] = (Z[76]*Z[116]-Z[3]*Z[117])*Z[49];
  M[5][6] = -Z[54]*Z[3]*Z[118];
  M[5][7] = -(Z[78]*Z[114]+Z[23]*Z[115])*Z[56];
  M[5][8] = Z[58]*Z[23]*Z[118];
  M[5][9] = -(Z[80]*Z[116]-Z[23]*Z[117])*Z[62];
}

void V2_3__d__db__G__d__db__O3_0::Calculate_M6()
{
  M[6][2] = (Z[103]*Z[83]-Z[101]*Z[61])*Z[26];
  M[6][3] = -Z[127]*Z[37];
  M[6][7] = -(Z[91]*Z[114]+Z[61]*Z[115])*Z[56];
  M[6][8] = Z[58]*Z[61]*Z[118];
  M[6][9] = Z[62]*Z[61]*Z[117];
}

void V2_3__d__db__G__d__db__O3_0::Calculate_M7()
{
  M[7][2] = (Z[121]*Z[83]-Z[101]*Z[82])*Z[26];
  M[7][3] = -Z[130]*Z[37];
  M[7][7] = -(Z[99]*Z[114]+Z[82]*Z[115])*Z[56];
  M[7][8] = Z[58]*Z[82]*Z[118];
  M[7][9] = Z[62]*Z[82]*Z[117];
}

void V2_3__d__db__G__d__db__O3_0::Calculate_M8()
{
  M[8][0] = Z[9]*Z[2]*Z[42];
  M[8][1] = Z[135]*Z[21];
  M[8][4] = (Z[40]*Z[136]+Z[42]*Z[41])*Z[44];
  M[8][5] = -Z[49]*Z[42]*Z[47];
  M[8][6] = -(Z[42]*Z[50]+Z[138]*Z[51])*Z[54];
}

void V2_3__d__db__G__d__db__O3_0::Calculate_M9()
{
  M[9][0] = Z[9]*Z[2]*Z[75];
  M[9][1] = Z[144]*Z[21];
  M[9][4] = (Z[74]*Z[136]+Z[75]*Z[41])*Z[44];
  M[9][5] = -Z[49]*Z[75]*Z[47];
  M[9][6] = -(Z[75]*Z[50]+Z[146]*Z[51])*Z[54];
}

