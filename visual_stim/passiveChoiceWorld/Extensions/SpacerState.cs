using Bonsai;
using System;
using System.ComponentModel;
using System.Collections.Generic;
using System.Linq;
using System.Reactive.Linq;
using Bonsai.Shaders;

[Combinator]
[Description("")]
[WorkflowElementCategory(ElementCategory.Transform)]
public class SpacerState
{
    static readonly int[] spacerFrames = new[] { 1, 2, 4, 8, 16, 32, 64, 128, 192, 224, 240, 248, 252, 254, 255 };

    public IObservable<float> Process(IObservable<FrameEvent> source)
    {
        return Observable.Defer(() =>
        {
            var totalTime = 0.0;
            var currentSpacer = 0;
            return source.Select(value =>
            {
                var timeStep = value.TimeStep.ElapsedTime;
                while (currentSpacer < spacerFrames.Length &&
                       totalTime >= spacerFrames[currentSpacer] * timeStep)
                {
                    currentSpacer++;
                }
                totalTime += timeStep;
                return currentSpacer;
            })
            .TakeWhile(spacer => spacer < spacerFrames.Length)
            .Select(spacer => spacer % 2 == 0 ? 1f : 0f);
        });
    }
}
