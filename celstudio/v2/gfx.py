"""Texture helper: manual half-size chain so CPU drawing can use fast bilinear sampling at any scale."""
import math
import skia

LINEAR = skia.SamplingOptions(skia.FilterMode.kLinear)


class Tex:
    def __init__(self, image):
        surface = skia.Surface(image.width(), image.height())
        surface.getCanvas().drawImage(image, 0, 0)
        self.levels = [surface.makeImageSnapshot()]
        self.w, self.h = image.width(), image.height()
        while min(self.levels[-1].width(), self.levels[-1].height()) >= 16 and len(self.levels) < 6:
            last = self.levels[-1]
            w, h = max(1, last.width()//2), max(1, last.height()//2)
            half = skia.Surface(w, h)
            half.getCanvas().drawImageRect(last, skia.Rect.MakeWH(last.width(), last.height()), skia.Rect.MakeWH(w, h), LINEAR)
            self.levels.append(half.makeImageSnapshot())

    @classmethod
    def open(cls, path):
        image = skia.Image.open(str(path))
        if image is None:
            raise FileNotFoundError(str(path))
        return cls(image)

    def width(self):
        return self.w

    def height(self):
        return self.h

    def level(self, canvas, extra=1.0):
        m = canvas.getTotalMatrix()
        scale = math.sqrt(abs(m.getScaleX()*m.getScaleY()-m.getSkewX()*m.getSkewY()))*extra
        index = 0 if scale >= 1 else min(len(self.levels)-1, int(math.log2(1/max(scale, 1e-6))))
        return index, self.levels[index]

    def draw(self, canvas, x=0.0, y=0.0, paint=None):
        index, image = self.level(canvas)
        if image.width() == self.w:
            canvas.drawImage(image, x, y, LINEAR, paint)
            return
        canvas.drawImageRect(image, skia.Rect.MakeWH(image.width(), image.height()), skia.Rect.MakeXYWH(x, y, self.w, self.h), LINEAR, paint)

    def blurred(self, sigma):
        """Cached pre-blurred copy (sigma in source pixels, quantised), computed at reduced resolution."""
        bucket = round(math.log(max(sigma, .05))*12)
        cache = self.__dict__.setdefault('_blur', {})
        if bucket not in cache:
            sigma = math.exp(bucket/12)
            index = max(0, min(len(self.levels)-1, int(math.log2(max(1.0, sigma/1.6)))))
            source = self.levels[index]
            local = sigma*source.width()/self.w
            surface = skia.Surface(source.width(), source.height())
            paint = skia.Paint()
            paint.setImageFilter(skia.ImageFilters.Blur(local, local, skia.TileMode.kClamp))
            surface.getCanvas().drawImage(source, 0, 0, LINEAR, paint)
            copy = Tex.__new__(Tex)
            copy.levels, copy.w, copy.h = [surface.makeImageSnapshot()], self.w, self.h
            cache[bucket] = copy
        return cache[bucket]

    def draw_rect(self, canvas, source, destination, paint=None):
        x0, y0, x1, y1 = source
        index, image = self.level(canvas, max(1e-6, destination.width()/max(1e-6, x1-x0)))
        fx, fy = image.width()/self.w, image.height()/self.h
        canvas.drawImageRect(image, skia.Rect.MakeLTRB(x0*fx, y0*fy, x1*fx, y1*fy), destination, LINEAR, paint)

    def shader(self, canvas):
        index, image = self.level(canvas)
        matrix = skia.Matrix.Scale(self.w/image.width(), self.h/image.height())
        return image.makeShader(skia.TileMode.kClamp, skia.TileMode.kClamp, LINEAR, matrix)
