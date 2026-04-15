#include "V.H"

using namespace AMEGIC;
using namespace ATOOLS;
using namespace std;

void V2_2__d__ub__d__ub__O2_0__E3::SetCouplFlav(vector<Complex>& coupl)
{
  f[0] = 21;

  for (int i=0;i<1;i++) c[i] = coupl[i];
  for (int i=0;i<16;i++)
    for (int j=0;j<1;j++) M[i][j] = Complex(0.,0.);

  Z[0] = Complex(0.,0.);
}

void V2_2__d__ub__d__ub__O2_0__E3::Calculate()
{
  for(int i=0;i<16;i++) cl[i] = 0;

  Z[1] = ZT<-1,-1,-1,-1>(2,0,1,3,c[0],c[0],c[0],c[0]);
  Z[2] = Pcalc(f[0],4);
  Z[3] = ZT<1,1,-1,-1>(2,0,1,3,c[0],c[0],c[0],c[0]);
  Z[4] = ZT<-1,-1,1,1>(2,0,1,3,c[0],c[0],c[0],c[0]);
  Z[5] = ZT<1,1,1,1>(2,0,1,3,c[0],c[0],c[0],c[0]);
}
