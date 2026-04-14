#include "V.H"

using namespace AMEGIC;
using namespace ATOOLS;
using namespace std;

extern "C" Values* Getter_V2_2__u__ub__em__ep__O0_2__E0(Basic_Sfuncs* bs) {
  return new V2_2__u__ub__em__ep__O0_2__E0(bs);
}

V2_2__u__ub__em__ep__O0_2__E0::V2_2__u__ub__em__ep__O0_2__E0(Basic_Sfuncs* _BS) :
     Basic_Func(0,_BS),
     Basic_Zfunc(0,_BS),
     Basic_Pfunc(0,_BS)
{
  f = new int[2];
  c = new Complex[6];
  Z = new Complex[14];
  M = new Complex*[16];
  for(int i=0;i<16;i++) M[i] = new Complex[2];
  cl = new int[16];
}

V2_2__u__ub__em__ep__O0_2__E0::~V2_2__u__ub__em__ep__O0_2__E0()
{
  if (Z)  delete[] Z;
  if (f)  delete[] f;
  if (c)  delete[] c;
  if (cl) delete[] cl;
  if (M) {
    for(int i=0;i<16;i++) delete[] M[i];
    delete[] M;
  }
}

Complex V2_2__u__ub__em__ep__O0_2__E0::Evaluate(int m,int n)
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
  }
  cl[n]=1;
  return M[n][m];
}

void V2_2__u__ub__em__ep__O0_2__E0::Calculate_M0()
{
  M[0][0] = -Z[1]*Z[2];
  M[0][1] = -Z[5]*Z[6];
}

void V2_2__u__ub__em__ep__O0_2__E0::Calculate_M1()
{
}

void V2_2__u__ub__em__ep__O0_2__E0::Calculate_M2()
{
}

void V2_2__u__ub__em__ep__O0_2__E0::Calculate_M3()
{
  M[3][0] = -Z[7]*Z[2];
  M[3][1] = -Z[9]*Z[6];
}

void V2_2__u__ub__em__ep__O0_2__E0::Calculate_M4()
{
}

void V2_2__u__ub__em__ep__O0_2__E0::Calculate_M5()
{
}

void V2_2__u__ub__em__ep__O0_2__E0::Calculate_M6()
{
}

void V2_2__u__ub__em__ep__O0_2__E0::Calculate_M7()
{
}

void V2_2__u__ub__em__ep__O0_2__E0::Calculate_M8()
{
}

void V2_2__u__ub__em__ep__O0_2__E0::Calculate_M9()
{
}

void V2_2__u__ub__em__ep__O0_2__E0::Calculate_M10()
{
}

void V2_2__u__ub__em__ep__O0_2__E0::Calculate_M11()
{
}

void V2_2__u__ub__em__ep__O0_2__E0::Calculate_M12()
{
  M[12][0] = -Z[10]*Z[2];
  M[12][1] = -Z[11]*Z[6];
}

void V2_2__u__ub__em__ep__O0_2__E0::Calculate_M13()
{
}

void V2_2__u__ub__em__ep__O0_2__E0::Calculate_M14()
{
}

void V2_2__u__ub__em__ep__O0_2__E0::Calculate_M15()
{
  M[15][0] = -Z[12]*Z[2];
  M[15][1] = -Z[13]*Z[6];
}

