"""Regression checks for bright cutout speckles and discoloured warped edges."""
from types import SimpleNamespace

import numpy as np
import pytest

skia=pytest.importorskip('skia')
from celstudio.v2.gfx import Tex
from celstudio.v2.puppet import Rig
from celstudio.v2.stage import Stage, View


@pytest.mark.parametrize('fringe',[(255,255,255),(255,160,60)])
def test_contour_does_not_turn_faint_fringe_into_opaque_speckle(fringe):
    pixels=np.zeros((16,16,4),dtype=np.uint8)
    pixels[4:12,6:12]=(180,70,25,255)
    pixels[7,5]=(*fringe,1)        # Nearly invisible white/matte contamination.
    pixels[7,9]=(255,255,255,255) # Intended interior white must survive.
    image=skia.Image.fromarray(pixels,colorType=skia.kRGBA_8888_ColorType)
    rig=SimpleNamespace(colors={'outline':'#311605'},pose=lambda *_:{},
                        draw=lambda canvas,*_:canvas.drawImage(image,-8,-20))
    values=dict(opacity=1,scale=1,x=32,y=40,rot=0,sx=1,sy=1,facing=1)
    performer=SimpleNamespace(rig=rig,drawing=lambda *_:(values,{}))
    stage=Stage.__new__(Stage)
    stage.width=stage.height=64
    stage.fps=24
    stage.k=1
    surface=skia.Surface(64,64)
    stage._actor(surface.getCanvas(),performer,0,View(64,64,64,64,32,32),{},
                 {'contour':1,'boil':0})
    result=surface.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)
    edge=result[27,29]
    assert edge[3]==255
    assert np.max(np.abs(edge[:3].astype(int)-[49,22,5]))<=2
    assert tuple(result[27,33])==(255,255,255,255)


@pytest.mark.parametrize('scale',[1,.45])
def test_mesh_sampling_preserves_colour_of_translucent_pixels(scale):
    pixels=np.zeros((32,32,4),dtype=np.uint8)
    pixels[4:28,4:28]=(200,80,20,128)
    tex=Tex(skia.Image.fromarray(pixels,colorType=skia.kRGBA_8888_ColorType))
    rig=Rig.__new__(Rig)
    rig._images={}
    surface=skia.Surface(40,40)
    canvas=surface.getCanvas()
    canvas.scale(scale,scale)
    images,_=rig._warp(canvas,[(tex,None)],lambda x,y:(x,y),(0,0,32,32))
    result=images[0][0].toarray(colorType=skia.kRGBA_8888_ColorType)
    centre=result[result.shape[0]//2,result.shape[1]//2]
    assert abs(int(centre[3])-128)<=1
    assert np.max(np.abs(centre[:3].astype(int)-[200,80,20]))<=2
