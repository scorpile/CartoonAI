"""CLI: python -m celstudio.v2 render|frame|sheet <film.json> ... | compile <project|episode> | new-series | new-episode | series-convert"""
import argparse
import json
import sys
from pathlib import Path
from .stage import Stage, load_film, render_film, frame_count


def main():
    parser = argparse.ArgumentParser(prog='celstudio.v2')
    sub = parser.add_subparsers(dest='command', required=True)
    r = sub.add_parser('render')
    r.add_argument('film'); r.add_argument('--output', required=True); r.add_argument('--width', type=int)
    r.add_argument('--shot', action='append'); r.add_argument('--workers', type=int); r.add_argument('--motion-blur', type=int)
    r.add_argument('--crf', type=int, default=20)
    f = sub.add_parser('frame')
    f.add_argument('film'); f.add_argument('--shot', required=True); f.add_argument('--time', type=float, default=0.0)
    f.add_argument('--output', required=True); f.add_argument('--width', type=int)
    s = sub.add_parser('sheet', help='Contact sheet: N evenly spaced frames per shot')
    s.add_argument('film'); s.add_argument('--output', required=True); s.add_argument('--shot', action='append')
    s.add_argument('--columns', type=int, default=6); s.add_argument('--width', type=int, default=480)
    s.add_argument('--step', type=float, default=0.0, help='seconds between frames (0 = columns per shot)')
    c = sub.add_parser('compile', help='Compile <project>/script.json into <project>/film.json (a film, or an episode: projects/<serie>/episodes/<ep>)')
    c.add_argument('project')
    n = sub.add_parser('new-series', help='Create projects/<id>/series.json with an empty shared library')
    n.add_argument('id'); n.add_argument('--title', default=''); n.add_argument('--projects', default='projects')
    e = sub.add_parser('new-episode', help='Create projects/<serie>/episodes/<ep>/script.json')
    e.add_argument('series'); e.add_argument('episode'); e.add_argument('--title', default=''); e.add_argument('--projects', default='projects')
    v = sub.add_parser('series-convert', help='Turn a single film into a series with one episode (ep01)')
    v.add_argument('project')
    args = parser.parse_args()
    if args.command in ('compile', 'new-series', 'new-episode', 'series-convert'):
        from . import project
        try:
            if args.command == 'new-series':
                print(json.dumps({'series': str(project.create_series(args.projects, args.id, args.title))}))
                return
            if args.command == 'new-episode':
                root = Path(args.series) if (Path(args.series)/'series.json').is_file() else Path(args.projects)/args.series
                print(json.dumps({'episode': str(project.create_episode(root, args.episode, args.title))}))
                return
            if args.command == 'series-convert':
                root = project.convert_series(project.normalize(args.project))
                print(json.dumps({'series': str(root), 'episode': str(root/'episodes'/'ep01')}))
                return
            film, target = project.compile_project(args.project)
            for w in project.warnings(None, project.normalize(args.project)):
                print(f"aviso {w['path']}: {w['message']}", file=sys.stderr)
        except project.ScriptError as e:
            raise SystemExit(str(e))
        print(json.dumps({'film': str(target), 'shots': len(film['shots']), 'seconds': round(sum(s['duration'] for s in film['shots']), 3),
                          'kb': target.stat().st_size//1024}))
        return
    if args.command == 'render':
        print(json.dumps(render_film(args.film, args.output, args.width, args.shot, args.workers, args.motion_blur, args.crf)))
        return
    film, root = load_film(args.film)
    if args.command == 'frame':
        stage = Stage(film, root, args.width)
        shot = next(x for x in film['shots'] if x['id'] == args.shot)
        stage.frame(shot, args.time).save(args.output)
        return
    import skia
    from .stage import contact_sheet
    image = contact_sheet(film, root, args.shot, args.columns, args.width, args.step)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    image.save(args.output, skia.kJPEG if args.output.lower().endswith('jpg') else skia.kPNG)


if __name__ == '__main__':
    main()
