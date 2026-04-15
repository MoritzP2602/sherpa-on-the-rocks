#include "V.H"

using namespace AMEGIC;
using namespace ATOOLS;
using namespace std;

extern "C" Values* Getter_V2_3__d__d__G__d__d__O3_0(Basic_Sfuncs* bs) {
  return new V2_3__d__d__G__d__d__O3_0(bs);
}

V2_3__d__d__G__d__d__O3_0::V2_3__d__d__G__d__d__O3_0(Basic_Sfuncs* _BS) :
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

V2_3__d__d__G__d__d__O3_0::~V2_3__d__d__G__d__d__O3_0()
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

Complex V2_3__d__d__G__d__d__O3_0::Evaluate(int m,int n)
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

void V2_3__d__d__G__d__d__O3_0::Calculate_M0()
{
  M[0][0] = Z[7]*Z[4]*Z[3];
  M[0][1] = -(Z[10]*Z[9]-Z[4]*Z[8])*Z[12];
  M[0][2] = -Z[19]*Z[16]*Z[15];
  M[0][3] = (Z[20]*Z[9]-Z[16]*Z[8])*Z[21];
  M[0][4] = Z[26]*Z[4]*Z[15];
  M[0][5] = -Z[31]*Z[16]*Z[3];
  M[0][6] = -(Z[35]*Z[34]-Z[32]*Z[4])*Z[38];
  M[0][7] = Z[48]*Z[49];
  M[0][8] = (Z[35]*Z[51]-Z[32]*Z[16])*Z[52];
  M[0][9] = -Z[61]*Z[62];
}

void V2_3__d__d__G__d__d__O3_0::Calculate_M1()
{
  M[1][0] = Z[7]*Z[33]*Z[3];
  M[1][1] = -(Z[64]*Z[9]-Z[33]*Z[8])*Z[12];
  M[1][2] = -Z[19]*Z[50]*Z[15];
  M[1][3] = (Z[66]*Z[9]-Z[50]*Z[8])*Z[21];
  M[1][4] = Z[26]*Z[33]*Z[15];
  M[1][5] = -Z[31]*Z[50]*Z[3];
  M[1][6] = -(Z[73]*Z[34]-Z[32]*Z[33])*Z[38];
  M[1][7] = Z[78]*Z[49];
  M[1][8] = (Z[73]*Z[51]-Z[32]*Z[50])*Z[52];
  M[1][9] = -Z[82]*Z[62];
}

void V2_3__d__d__G__d__d__O3_0::Calculate_M2()
{
}

void V2_3__d__d__G__d__d__O3_0::Calculate_M3()
{
}

void V2_3__d__d__G__d__d__O3_0::Calculate_M4()
{
  M[4][0] = (Z[2]*Z[92]+Z[4]*Z[93])*Z[7];
  M[4][1] = Z[12]*Z[4]*Z[94];
  M[4][2] = -(Z[14]*Z[96]+Z[16]*Z[97])*Z[19];
  M[4][3] = -Z[21]*Z[16]*Z[94];
  M[4][4] = (Z[22]*Z[96]+Z[4]*Z[97])*Z[26];
  M[4][5] = -(Z[27]*Z[92]+Z[16]*Z[93])*Z[31];
  M[4][6] = Z[38]*Z[98]*Z[4];
  M[4][7] = Z[105]*Z[49];
  M[4][8] = -Z[52]*Z[98]*Z[16];
  M[4][9] = -Z[110]*Z[62];
}

void V2_3__d__d__G__d__d__O3_0::Calculate_M5()
{
  M[5][0] = (Z[63]*Z[92]+Z[33]*Z[93])*Z[7];
  M[5][1] = Z[12]*Z[33]*Z[94];
  M[5][2] = -(Z[65]*Z[96]+Z[50]*Z[97])*Z[19];
  M[5][3] = -Z[21]*Z[50]*Z[94];
  M[5][4] = (Z[67]*Z[96]+Z[33]*Z[97])*Z[26];
  M[5][5] = -(Z[70]*Z[92]+Z[50]*Z[93])*Z[31];
  M[5][6] = Z[38]*Z[98]*Z[33];
  M[5][7] = Z[114]*Z[49];
  M[5][8] = -Z[52]*Z[98]*Z[50];
  M[5][9] = -Z[116]*Z[62];
}

void V2_3__d__d__G__d__d__O3_0::Calculate_M6()
{
}

void V2_3__d__d__G__d__d__O3_0::Calculate_M7()
{
}

void V2_3__d__d__G__d__d__O3_0::Calculate_M8()
{
  M[8][2] = -Z[19]*Z[29]*Z[15];
  M[8][3] = (Z[121]*Z[9]-Z[29]*Z[8])*Z[21];
  M[8][5] = -(Z[28]*Z[118]+Z[29]*Z[3])*Z[31];
  M[8][8] = -Z[52]*Z[32]*Z[29];
  M[8][9] = -Z[126]*Z[62];
}

void V2_3__d__d__G__d__d__O3_0::Calculate_M9()
{
  M[9][2] = -Z[19]*Z[72]*Z[15];
  M[9][3] = (Z[129]*Z[9]-Z[72]*Z[8])*Z[21];
  M[9][5] = -(Z[71]*Z[118]+Z[72]*Z[3])*Z[31];
  M[9][8] = -Z[52]*Z[32]*Z[72];
  M[9][9] = -Z[133]*Z[62];
}

void V2_3__d__d__G__d__d__O3_0::Calculate_M10()
{
  M[10][0] = (Z[83]*Z[118]+Z[84]*Z[3])*Z[7];
  M[10][1] = Z[12]*Z[84]*Z[8];
  M[10][4] = Z[26]*Z[84]*Z[15];
  M[10][6] = -(Z[35]*Z[139]-Z[32]*Z[84])*Z[38];
  M[10][7] = Z[143]*Z[49];
}

void V2_3__d__d__G__d__d__O3_0::Calculate_M11()
{
  M[11][0] = (Z[88]*Z[118]+Z[89]*Z[3])*Z[7];
  M[11][1] = Z[12]*Z[89]*Z[8];
  M[11][4] = Z[26]*Z[89]*Z[15];
  M[11][6] = -(Z[73]*Z[139]-Z[32]*Z[89])*Z[38];
  M[11][7] = Z[149]*Z[49];
}

void V2_3__d__d__G__d__d__O3_0::Calculate_M12()
{
  M[12][2] = -(Z[120]*Z[96]+Z[29]*Z[97])*Z[19];
  M[12][3] = -Z[21]*Z[29]*Z[94];
  M[12][5] = -Z[31]*Z[29]*Z[93];
  M[12][8] = (Z[100]*Z[122]-Z[98]*Z[29])*Z[52];
  M[12][9] = -Z[152]*Z[62];
}

